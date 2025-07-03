"""tests for the core fetch_abstract module in app/fetch_abstract.py."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from app.data_models.generic import (
    AbstractNotFoundError,
    AbstractUnpackError,
    AbstractUnpackStrategy,
    APIConfig,
    ExternalAPI,
    external_api_priority,
)
from app.fetch_abstract import AbstractFetcher, prepare_api_config
from app.utils import InvalidDOIError


@pytest.fixture
def scopus_api_config():
    return APIConfig(
        name=ExternalAPI.SCOPUS,
        url="https://api.example.com/",
        api_key_env_var_name="elsevier_scopus_key",  # pragma: allowlist secret
        api_key_placement="X-API-Key",  # pragma: allowlist secret
        query_params={},
        headers={"X-API-Key": ""},
        unpack_strategy=AbstractUnpackStrategy(
            source=ExternalAPI.SCOPUS, strategy=["data", "abstract"]
        ),
    )


@pytest.fixture
def wos_api_config():
    return APIConfig(
        name=ExternalAPI.WEB_OF_SCIENCE,
        url="https://api.example.com/",
        api_key_env_var_name="wos_key",  # pragma: allowlist secret
        api_key_placement="wos_key",  # pragma: allowlist secret
        query_params={},
        headers={"wos_key": ""},
        unpack_strategy=AbstractUnpackStrategy(
            source=ExternalAPI.WEB_OF_SCIENCE, strategy=["text", "meta", "abstract"]
        ),
    )


# NOTE - add more config fixtures here as we develop them
# NOTE - right now, `wos_api_config` is a standin for a missing API key style config


def test_prepare_api_config_success(scopus_api_config, test_settings):
    configs = [scopus_api_config]
    result = prepare_api_config(
        configs, test_settings, external_api_priority=external_api_priority
    )
    assert "SCOPUS" in result
    assert result["SCOPUS"].headers["X-API-Key"] == "dummy_scopus_key"


def test_prepare_api_config_missing_key(wos_api_config, test_settings):
    # NOTE - wos_api_config here is defined as missing a key.
    # if this is ever functional, we shold explicitly populate
    # a fixture with missing credentials.
    configs = [wos_api_config]
    result = prepare_api_config(
        configs, test_settings, external_api_priority=external_api_priority
    )
    assert result == {}


def test_abstract_fetcher_init_logs(scopus_api_config):
    with patch("app.fetch_abstract.logger") as mock_logger:
        fetcher = AbstractFetcher({"SCOPUS": scopus_api_config})
        mock_logger.info.assert_any_call(
            "available external APIs, in descending order of priority:"
        )
        mock_logger.info.assert_any_call("SCOPUS")
        assert fetcher.timeout == 60


def test_fetch_success(scopus_api_config, test_settings):
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([scopus_api_config], test_settings)
    )
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"foo": "bar"}
    with patch("requests.get", return_value=mock_response) as mock_get:
        result = fetcher.fetch("http://test", {}, {})
        assert result == {"foo": "bar"}
        mock_get.assert_called_once()


def test_fetch_http_error(scopus_api_config, test_settings):
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([scopus_api_config], test_settings)
    )
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.HTTPError("fail")
    with (
        patch("requests.get", return_value=mock_response),
        pytest.raises(requests.HTTPError),
    ):
        fetcher.fetch("http://test", {}, {})


def test_unpack_abstract_success(scopus_api_config, test_settings):
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([scopus_api_config], test_settings)
    )
    response_obj = {"data": {"abstract": "This is the abstract."}}
    result = fetcher.unpack_abstract(
        response_obj, strategy=fetcher.master_api_config["SCOPUS"].unpack_strategy
    )
    assert result == "This is the abstract."


def test_unpack_abstract_keyerror(scopus_api_config, test_settings):
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([scopus_api_config], test_settings)
    )
    response_obj = {"data": {"foo": "bar"}}
    with pytest.raises(AbstractUnpackError):
        fetcher.unpack_abstract(
            response_obj, strategy=fetcher.master_api_config["SCOPUS"].unpack_strategy
        )


def test_fetch_one_abstract_success(scopus_api_config, test_settings):
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([scopus_api_config], test_settings)
    )
    doi = "10.1000/xyz123"
    with (
        patch("app.fetch_abstract.validate_doi", return_value=True),
        patch.object(fetcher, "fetch", return_value={"data": {"abstract": "abc"}}),
        patch.object(fetcher, "unpack_abstract", return_value="abc"),
    ):
        result = fetcher.fetch_one_abstract(doi, scopus_api_config)
        assert result == "abc"


def test_fetch_one_abstract_invalid_doi(scopus_api_config, test_settings):
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([scopus_api_config], test_settings)
    )
    with (
        patch("app.fetch_abstract.validate_doi", return_value=False),
        pytest.raises(InvalidDOIError),
    ):
        fetcher.fetch_one_abstract("bad-doi", scopus_api_config)


def test_fetch_one_abstract_http_error(scopus_api_config, test_settings):
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([scopus_api_config], test_settings)
    )
    with (
        patch("app.fetch_abstract.validate_doi", return_value=True),
        patch.object(fetcher, "fetch", side_effect=requests.HTTPError("fail")),
        pytest.raises(requests.HTTPError),
    ):
        fetcher.fetch_one_abstract("10.1000/xyz123", scopus_api_config)


def test_fetch_one_abstract_unpack_error(scopus_api_config, test_settings):
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([scopus_api_config], test_settings)
    )
    with (
        patch("app.fetch_abstract.validate_doi", return_value=True),
        patch.object(fetcher, "fetch", return_value={"data": {}}),
        patch.object(
            fetcher, "unpack_abstract", side_effect=AbstractUnpackError("fail")
        ),
        pytest.raises(AbstractUnpackError),
    ):
        fetcher.fetch_one_abstract("10.1000/xyz123", scopus_api_config)


def test_get_abstract_cycling_apis_success(scopus_api_config, test_settings):
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([scopus_api_config], test_settings)
    )
    with patch.object(fetcher, "fetch_one_abstract", return_value="abstract text"):
        result = fetcher.get_abstract_cycling_apis("10.1000/xyz123")
        assert result == "abstract text"


def test_get_abstract_cycling_apis_not_found(scopus_api_config, test_settings):
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([scopus_api_config], test_settings)
    )
    with (
        patch.object(fetcher, "fetch_one_abstract", return_value=None),
        pytest.raises(AbstractNotFoundError),
    ):
        fetcher.get_abstract_cycling_apis("10.1000/xyz123")


def test_get_abstract_cycling_apis_invalid_doi(scopus_api_config, test_settings):
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([scopus_api_config], test_settings)
    )
    with (
        patch.object(fetcher, "fetch_one_abstract", side_effect=InvalidDOIError("bad")),
        pytest.raises(InvalidDOIError),
    ):
        fetcher.get_abstract_cycling_apis("bad-doi")
