"""tests for the core fetch_abstract module in app/fetch_abstract.py."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from app.config import get_settings
from app.data_models.generic import (
    AbstractNotFoundError,
    AbstractUnpackError,
    external_api_priority,
)
from app.fetch_abstract import AbstractFetcher, prepare_api_config
from app.utils import InvalidDOIError


def test_prepare_api_config_success(scopus_api_config_valid, crossref_api_config_valid):
    settings = get_settings()
    configs = [scopus_api_config_valid, crossref_api_config_valid]
    result = prepare_api_config(
        configs, settings, external_api_priority=external_api_priority
    )
    assert "SCOPUS" in result
    assert "CROSSREF" in result
    assert not result["SCOPUS"].unpack_strategy.clean_abstract_string
    assert result["SCOPUS"].headers["X-API-Key"] == "dummy_scopus_key"
    assert result["CROSSREF"].headers == {"Accept": "application/json"}
    assert result["CROSSREF"].api_key_env_var_name is None
    assert result["CROSSREF"].unpack_strategy.clean_abstract_string


def test_prepare_api_config_missing_key(wos_api_config_invalid):
    settings = get_settings()
    # NOTE - wos_api_config here is defined as missing a key.
    # if this is ever functional, we shold explicitly populate
    # a fixture with missing credentials.
    configs = [wos_api_config_invalid]
    result = prepare_api_config(
        configs, settings, external_api_priority=external_api_priority
    )
    assert result == {}


def test_abstract_fetcher_init_logs(scopus_api_config_valid):
    with patch("app.fetch_abstract.logger") as mock_logger:
        fetcher = AbstractFetcher({"SCOPUS": scopus_api_config_valid})
        mock_logger.info.assert_any_call(
            "available external APIs, in descending order of priority:"
        )
        mock_logger.info.assert_any_call("SCOPUS")
        assert fetcher.timeout == 60


@pytest.mark.parametrize(
    "api_config_fixture",
    [
        "scopus_api_config_valid",
        "crossref_api_config_valid",
    ],
)
def test_fetch_success(request, api_config_fixture):
    settings = get_settings()
    api_config = request.getfixturevalue(api_config_fixture)
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([api_config], settings)
    )
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"foo": "bar"}
    with patch("requests.get", return_value=mock_response) as mock_get:
        result = fetcher.fetch("http://test", {}, {})
        assert result == {"foo": "bar"}
        mock_get.assert_called_once()


def test_fetch_http_error(scopus_api_config_valid):
    settings = get_settings()
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([scopus_api_config_valid], settings)
    )
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.HTTPError("fail")
    with (
        patch("requests.get", return_value=mock_response),
        pytest.raises(requests.HTTPError),
    ):
        fetcher.fetch("http://test", {}, {})


def test_unpack_abstract_success(scopus_api_config_valid):
    settings = get_settings()
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([scopus_api_config_valid], settings)
    )
    response_obj = {"data": {"abstract": "This is the abstract."}}
    result = fetcher.unpack_abstract(
        response_obj, strategy=fetcher.master_api_config["SCOPUS"].unpack_strategy
    )
    assert result == "This is the abstract."


def test_unpack_abstract_keyerror(scopus_api_config_valid):
    settings = get_settings()
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([scopus_api_config_valid], settings)
    )
    response_obj = {"data": {"foo": "bar"}}
    with pytest.raises(AbstractUnpackError):
        fetcher.unpack_abstract(
            response_obj, strategy=fetcher.master_api_config["SCOPUS"].unpack_strategy
        )


def test_clean_abstract_string_removes_jats_tags():
    raw = "<jats:p>This is a <b>test</b> abstract.</jats:p>"
    cleaned = AbstractFetcher.clean_abstract_string(raw)
    assert cleaned == "This is a <b>test</b> abstract."


def test_unpack_abstract_with_cleaning(crossref_api_config_valid):
    fetcher = AbstractFetcher({"CROSSREF": crossref_api_config_valid})
    response_obj = {"text": {"meta": {"abstract": "<jats:p>Clean me!</jats:p>"}}}

    result = fetcher.unpack_abstract(
        response_obj, strategy=fetcher.master_api_config["CROSSREF"].unpack_strategy
    )
    assert result == "Clean me!"


def test_fetch_one_abstract_success(crossref_api_config_valid, scopus_api_config_valid):
    settings = get_settings()
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config(
            [crossref_api_config_valid, scopus_api_config_valid], settings
        )
    )
    doi = "10.1000/xyz123"
    with (
        patch("app.fetch_abstract.validate_doi", return_value=True),
        patch.object(
            fetcher,
            "fetch",
            return_value={"text": {"meta": {"abstract": "<jats:p>abc</jats:p>"}}},
        ),
    ):
        result = fetcher.fetch_one_abstract(doi, crossref_api_config_valid)
        assert result == "abc"


def test_fetch_one_abstract_invalid_doi(scopus_api_config_valid):
    settings = get_settings()
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([scopus_api_config_valid], settings)
    )
    with (
        patch("app.fetch_abstract.validate_doi", return_value=False),
        pytest.raises(InvalidDOIError),
    ):
        fetcher.fetch_one_abstract("bad-doi", scopus_api_config_valid)


def test_fetch_one_abstract_http_error(scopus_api_config_valid):
    settings = get_settings()
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([scopus_api_config_valid], settings)
    )
    with (
        patch("app.fetch_abstract.validate_doi", return_value=True),
        patch.object(fetcher, "fetch", side_effect=requests.HTTPError("fail")),
        pytest.raises(requests.HTTPError),
    ):
        fetcher.fetch_one_abstract("10.1000/xyz123", scopus_api_config_valid)


def test_fetch_one_abstract_unpack_error(scopus_api_config_valid):
    settings = get_settings()
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([scopus_api_config_valid], settings)
    )
    with (
        patch("app.fetch_abstract.validate_doi", return_value=True),
        patch.object(fetcher, "fetch", return_value={"data": {}}),
        patch.object(
            fetcher, "unpack_abstract", side_effect=AbstractUnpackError("fail")
        ),
        pytest.raises(AbstractUnpackError),
    ):
        fetcher.fetch_one_abstract("10.1000/xyz123", scopus_api_config_valid)


def test_get_abstract_cycling_apis_success(
    crossref_api_config_valid, scopus_api_config_valid
):
    settings = get_settings()
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config(
            [crossref_api_config_valid, scopus_api_config_valid], settings
        )
    )
    with patch.object(fetcher, "fetch_one_abstract", return_value="abstract text"):
        result = fetcher.get_abstract_cycling_apis("10.1000/xyz123")
        assert result == "abstract text"


def test_get_abstract_cycling_apis_not_found(
    crossref_api_config_valid, scopus_api_config_valid
):
    settings = get_settings()
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config(
            [crossref_api_config_valid, scopus_api_config_valid], settings
        )
    )
    with (
        patch.object(fetcher, "fetch_one_abstract", return_value=None),
        pytest.raises(AbstractNotFoundError),
    ):
        fetcher.get_abstract_cycling_apis("10.1000/xyz123")


def test_get_abstract_cycling_apis_invalid_doi(
    crossref_api_config_valid, scopus_api_config_valid
):
    settings = get_settings()
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config(
            [crossref_api_config_valid, scopus_api_config_valid], settings
        )
    )
    with (
        patch.object(fetcher, "fetch_one_abstract", side_effect=InvalidDOIError("bad")),
        pytest.raises(InvalidDOIError),
    ):
        fetcher.get_abstract_cycling_apis("bad-doi")
