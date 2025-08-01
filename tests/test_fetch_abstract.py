"""tests for the core fetch_abstract module in app/fetch_abstract.py."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from app.config import get_settings
from app.data_models.generic import AbstractNotFoundError, AbstractUnpackError
from app.fetch_abstract import AbstractFetcher, prepare_api_config
from app.utils import InvalidDOIError


def test_prepare_api_config_success(
    scopus_api_config_valid_single,
    scopus_api_config_valid_batch,
    crossref_api_config_valid_single,
    crossref_api_config_valid_batch,
    external_api_priorities,
):
    settings = get_settings()
    configs = [
        scopus_api_config_valid_single,
        scopus_api_config_valid_batch,
        crossref_api_config_valid_single,
        crossref_api_config_valid_batch,
    ]
    result = prepare_api_config(
        configs,
        settings,
        external_api_priority_single=external_api_priorities["single"],
        external_api_priority_batch=external_api_priorities["batch"],
    )
    single_results = result["single"]
    batch_results = result["batch"]
    assert set(single_results.keys()) == {"CROSSREF", "SCOPUS"}
    assert not single_results["SCOPUS"].unpack_strategy.clean_abstract_string
    assert single_results["SCOPUS"].headers["X-API-Key"] == "dummy_scopus_key"
    assert single_results["CROSSREF"].headers == {"Accept": "application/json"}
    assert single_results["CROSSREF"].api_key_env_var_name is None
    assert single_results["CROSSREF"].unpack_strategy.clean_abstract_string

    assert set(batch_results.keys()) == {"CROSSREF_BATCH", "SCOPUS_BATCH"}
    assert not batch_results["SCOPUS_BATCH"].unpack_strategy.clean_abstract_string
    assert batch_results["SCOPUS_BATCH"].headers["X-API-Key"] == "dummy_scopus_key"
    assert batch_results["CROSSREF_BATCH"].headers == {"Accept": "application/json"}
    assert batch_results["CROSSREF_BATCH"].api_key_env_var_name is None
    assert batch_results["CROSSREF_BATCH"].unpack_strategy.clean_abstract_string


def test_prepare_api_config_missing_key(external_api_priorities, invalid_api_config):
    settings = get_settings()
    configs = [invalid_api_config]
    result = prepare_api_config(
        configs,
        settings,
        external_api_priority_single=external_api_priorities["single"],
        external_api_priority_batch=external_api_priorities["batch"],
    )
    for value in result.values():
        assert value == {}


@pytest.mark.parametrize(
    "api_config_fixture",
    [
        {
            "single": "scopus_api_config_valid_single",
            "batch": "scopus_api_config_valid_batch",
        },
        {
            "single": "crossref_api_config_valid_single",
            "batch": "crossref_api_config_valid_batch",
        },
    ],
)
def test_abstract_fetcher_init_logs(request, api_config_fixture):
    api_config_single = request.getfixturevalue(api_config_fixture["single"])
    api_config_batch = request.getfixturevalue(api_config_fixture["batch"])
    settings = get_settings()
    with patch("app.fetch_abstract.logger") as mock_logger:
        master_api_config = prepare_api_config(
            [api_config_single, api_config_batch], settings
        )
        fetcher = AbstractFetcher(master_api_config)
        mock_logger.info.assert_any_call(
            "Available external APIs - SINGLE - in descending order of priority:"
        )
        mock_logger.info.assert_any_call(
            "Available external APIs - BATCH - in descending order of priority:"
        )
        for external_api_name in master_api_config["single"]:
            assert external_api_name == api_config_single.name.value.upper()
        for external_api_name in master_api_config["batch"]:
            assert external_api_name == api_config_batch.name.value.upper()
        assert fetcher.timeout == 60


@pytest.mark.parametrize(
    "api_config_fixture",
    [
        {
            "single": "scopus_api_config_valid_single",
            "batch": "scopus_api_config_valid_batch",
        },
        {
            "single": "crossref_api_config_valid_single",
            "batch": "crossref_api_config_valid_batch",
        },
    ],
)
def test_fetch_success(request, api_config_fixture):
    settings = get_settings()
    api_config_single = request.getfixturevalue(api_config_fixture["single"])
    api_config_batch = request.getfixturevalue(api_config_fixture["batch"])
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config(
            [api_config_single, api_config_batch], settings
        )
    )
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"foo": "bar"}
    with patch("requests.get", return_value=mock_response) as mock_get:
        result = fetcher.fetch("http://test", {}, {})
        assert result == {"foo": "bar"}
        mock_get.assert_called_once()


@pytest.mark.parametrize(
    "api_config_fixture",
    [
        {
            "single": "scopus_api_config_valid_single",
            "batch": "scopus_api_config_valid_batch",
        },
        {
            "single": "crossref_api_config_valid_single",
            "batch": "crossref_api_config_valid_batch",
        },
    ],
)
def test_fetch_http_error(request, api_config_fixture):
    settings = get_settings()
    api_config_single = request.getfixturevalue(api_config_fixture["single"])
    api_config_batch = request.getfixturevalue(api_config_fixture["batch"])
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config(
            [api_config_single, api_config_batch], settings
        )
    )
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.HTTPError("fail")
    with (
        patch("requests.get", return_value=mock_response),
        pytest.raises(requests.HTTPError),
    ):
        fetcher.fetch("http://test", {}, {})


@pytest.mark.parametrize(
    "api_config_fixture",
    [
        {
            "single": "scopus_api_config_valid_single",
        },
        {
            "single": "crossref_api_config_valid_single",
        },
    ],
)
def test_unpack_one_abstract_success(request, api_config_fixture):
    settings = get_settings()
    api_config_single = request.getfixturevalue(api_config_fixture["single"])
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([api_config_single], settings)
    )
    response_obj = {"data": {"abstract": "This is the abstract."}}
    external_api_name = api_config_single.name.value.upper()
    result = fetcher.unpack_one_abstract(
        response_obj,
        strategy=fetcher.master_api_config["single"][external_api_name].unpack_strategy,
    )
    assert result == "This is the abstract."


def test_unpack_many_abstracts_scopus_batch_success(scopus_api_config_valid_batch):
    settings = get_settings()
    api_config_batch = scopus_api_config_valid_batch
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([api_config_batch], settings)
    )
    test_doi_one = "10.1000/xyz123"
    test_doi_two = "10.1000/xyz124"
    test_abstract_one = "This is one abstract."
    test_abstract_two = "This is another abstract."
    test_mocked_response_entry_object = [
        {"prism:doi": test_doi_one, "dc:description": test_abstract_one},
        {"prism:doi": test_doi_two, "dc:description": test_abstract_two},
    ]
    test_response_obj = {"search-results": {"entry": test_mocked_response_entry_object}}
    external_api_name = api_config_batch.name.value.upper()
    result = fetcher.unpack_many_abstracts(
        test_response_obj,
        strategy=fetcher.master_api_config["batch"][external_api_name].unpack_strategy,
    )
    assert len(result) == len(test_mocked_response_entry_object)
    assert result[0]["doi"] == test_doi_one
    assert result[1]["doi"] == test_doi_two
    assert result[0]["abstract"] == test_abstract_one
    assert result[1]["abstract"] == test_abstract_two


@pytest.mark.parametrize(
    "api_config_fixture",
    [
        {
            "single": "scopus_api_config_valid_single",
        },
        {
            "single": "crossref_api_config_valid_single",
        },
    ],
)
def test_unpack_one_abstract_keyerror(request, api_config_fixture):
    settings = get_settings()
    api_config_single = request.getfixturevalue(api_config_fixture["single"])
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([api_config_single], settings)
    )
    response_obj = {"data": {"foo": "bar"}}
    with pytest.raises(AbstractUnpackError):
        fetcher.unpack_one_abstract(
            response_obj,
            strategy=fetcher.master_api_config["single"][
                api_config_single.name.value.upper()
            ].unpack_strategy,
        )


def test_traverse_non_dict_returns_none():
    # Should return None if input is not a dict
    result = AbstractFetcher._traverse("notadict", ["foo"])  # noqa: SLF001
    assert result is None


def test_traverse_missing_key_returns_none():
    # Should return None if key is missing
    d = {"foo": {"bar": 1}}
    result = AbstractFetcher._traverse(d, ["foo", "baz"])  # noqa: SLF001
    assert result is None


def test_unpack_many_abstracts_missing_doi_or_abstract(scopus_api_config_valid_batch):
    settings = get_settings()
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([scopus_api_config_valid_batch], settings)
    )
    # Entry missing abstract
    response_obj = {"search-results": {"entry": [{"prism:doi": "10.1000/xyz123"}]}}
    result = fetcher.unpack_many_abstracts(
        response_obj,
        strategy=fetcher.master_api_config["batch"]["SCOPUS_BATCH"].unpack_strategy,
    )
    assert result == []


def test_unpack_many_abstracts_empty_entries(scopus_api_config_valid_batch):
    """Should return empty list if entries is not a list (e.g., None or dict)."""
    settings = get_settings()
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([scopus_api_config_valid_batch], settings)
    )
    # entries is None
    response_obj = {"search-results": {"entry": None}}
    result = fetcher.unpack_many_abstracts(
        response_obj,
        strategy=fetcher.master_api_config["batch"]["SCOPUS_BATCH"].unpack_strategy,
    )
    assert result == []

    # entries is a dict, not a list
    response_obj = {"search-results": {"entry": {"prism:doi": "10.1000/xyz123"}}}
    result = fetcher.unpack_many_abstracts(
        response_obj,
        strategy=fetcher.master_api_config["batch"]["SCOPUS_BATCH"].unpack_strategy,
    )
    assert result == []


def test_unpack_many_abstracts_entry_missing_doi_and_abstract(
    scopus_api_config_valid_batch,
):
    """Should skip entries missing both DOI and abstract."""
    settings = get_settings()
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([scopus_api_config_valid_batch], settings)
    )
    # Entry missing both DOI and abstract
    response_obj = {"search-results": {"entry": [{}]}}
    result = fetcher.unpack_many_abstracts(
        response_obj,
        strategy=fetcher.master_api_config["batch"]["SCOPUS_BATCH"].unpack_strategy,
    )
    assert result == []


def test_unpack_many_abstracts_with_cleaning(crossref_api_config_valid_batch):
    """Should clean abstract string if clean_abstract_string is True."""
    settings = get_settings()
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config(
            [crossref_api_config_valid_batch], settings
        )
    )
    # Abstract contains tags, should be cleaned
    response_obj = {
        "message": {
            "items": [
                {
                    "DOI": "10.1000/xyz123",
                    "abstract": "<jats:p>Clean <b>me</b>!</jats:p>",
                }
            ]
        }
    }
    result = fetcher.unpack_many_abstracts(
        response_obj,
        strategy=fetcher.master_api_config["batch"]["CROSSREF_BATCH"].unpack_strategy,
    )
    assert result[0]["abstract"] == "Clean me!"


def test_unpack_many_abstracts_multiple_batches(scopus_api_config_valid_batch):
    """Should handle a list of batches as input."""
    settings = get_settings()
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([scopus_api_config_valid_batch], settings)
    )
    batch1 = {
        "search-results": {
            "entry": [{"prism:doi": "10.1000/xyz123", "dc:description": "A1"}]
        }
    }
    batch2 = {
        "search-results": {
            "entry": [{"prism:doi": "10.1000/xyz124", "dc:description": "A2"}]
        }
    }
    response_obj = [batch1, batch2]
    result = fetcher.unpack_many_abstracts(
        response_obj,
        strategy=fetcher.master_api_config["batch"]["SCOPUS_BATCH"].unpack_strategy,
    )
    assert len(result) == 2
    assert result[0]["doi"] == "10.1000/xyz123"
    assert result[1]["doi"] == "10.1000/xyz124"


def test_clean_abstract_string_removes_all_tags():
    raw = "<jats:p>This is a <b>test</b> abstract.</jats:p>"
    cleaned = AbstractFetcher.clean_abstract_string(raw)
    assert cleaned == "This is a test abstract."


def test_clean_abstract_string_fallback_regex():
    # invalid XML, should trigger the regex fallback
    raw = "<notclosed>This is broken"
    cleaned = AbstractFetcher.clean_abstract_string(raw)
    assert cleaned == "This is broken"


def test_process_doi_remove_url():
    raw = "https://doi.org/10.1109/pssgt64932.2025.11033854"
    cleaned = AbstractFetcher.process_doi(raw)
    assert cleaned == "10.1109/pssgt64932.2025.11033854"


def test_process_doi_tolower():
    raw = "10.1109/PSSGT64932.2025.11033854"
    cleaned = AbstractFetcher.process_doi(raw)
    assert cleaned == "10.1109/pssgt64932.2025.11033854"


def test_unpack_abstract_with_cleaning(crossref_api_config_valid_single):
    settings = get_settings()
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config(
            [crossref_api_config_valid_single], settings
        )
    )
    response_obj = {"data": {"abstract": "<jats:p>Clean me!</jats:p>"}}

    result = fetcher.unpack_one_abstract(
        response_obj,
        strategy=fetcher.master_api_config["single"]["CROSSREF"].unpack_strategy,
    )
    assert result == "Clean me!"


def test_fetch_one_abstract_success(
    crossref_api_config_valid_single, scopus_api_config_valid_single
):
    settings = get_settings()
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config(
            [crossref_api_config_valid_single, scopus_api_config_valid_single], settings
        )
    )
    doi = "10.1000/xyz123"
    with (
        patch("app.fetch_abstract.validate_doi", return_value=True),
        patch.object(
            fetcher,
            "fetch",
            return_value={"data": {"abstract": "<jats:p>abc</jats:p>"}},
        ),
    ):
        result = fetcher.fetch_one_abstract(doi, crossref_api_config_valid_single)
        assert result == {"abstract": "abc", "doi": doi}


def test_fetch_one_abstract_invalid_doi(scopus_api_config_valid_single):
    settings = get_settings()
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([scopus_api_config_valid_single], settings)
    )
    with (
        patch("app.fetch_abstract.validate_doi", return_value=False),
        pytest.raises(InvalidDOIError),
    ):
        fetcher.fetch_one_abstract("bad-doi", scopus_api_config_valid_single)


def test_fetch_one_abstract_http_error(scopus_api_config_valid_single):
    settings = get_settings()
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([scopus_api_config_valid_single], settings)
    )
    with (
        patch("app.fetch_abstract.validate_doi", return_value=True),
        patch.object(fetcher, "fetch", side_effect=requests.HTTPError("fail")),
        pytest.raises(requests.HTTPError),
    ):
        fetcher.fetch_one_abstract("10.1000/xyz123", scopus_api_config_valid_single)


def test_fetch_one_abstract_unpack_error(scopus_api_config_valid_single):
    settings = get_settings()
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([scopus_api_config_valid_single], settings)
    )
    with (
        patch("app.fetch_abstract.validate_doi", return_value=True),
        patch.object(fetcher, "fetch", return_value={"data": {}}),
        patch.object(
            fetcher, "unpack_one_abstract", side_effect=AbstractUnpackError("fail")
        ),
    ):
        doi_abstract_dict = fetcher.fetch_one_abstract(
            "10.1000/xyz123", scopus_api_config_valid_single
        )
        assert doi_abstract_dict is None


def test_get_one_abstract_cycling_apis_success(
    crossref_api_config_valid_single, scopus_api_config_valid_single
):
    settings = get_settings()
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config(
            [crossref_api_config_valid_single, scopus_api_config_valid_single], settings
        )
    )
    with patch.object(fetcher, "fetch_one_abstract", return_value="abstract text"):
        result = fetcher.get_one_abstract_cycling_apis("10.1000/xyz123")
        assert result == "abstract text"


def test_get_one_abstract_cycling_apis_not_found(
    crossref_api_config_valid_single, scopus_api_config_valid_single
):
    settings = get_settings()
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config(
            [crossref_api_config_valid_single, scopus_api_config_valid_single], settings
        )
    )
    with (
        patch.object(fetcher, "fetch_one_abstract", return_value=None),
        pytest.raises(AbstractNotFoundError),
    ):
        fetcher.get_one_abstract_cycling_apis("10.1000/xyz123")


def test_get_one_abstract_cycling_apis_invalid_doi(
    crossref_api_config_valid_single, scopus_api_config_valid_single
):
    settings = get_settings()
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config(
            [crossref_api_config_valid_single, scopus_api_config_valid_single], settings
        )
    )
    with (
        patch.object(fetcher, "fetch_one_abstract", side_effect=InvalidDOIError("bad")),
        pytest.raises(InvalidDOIError),
    ):
        fetcher.get_one_abstract_cycling_apis("bad-doi")


def test_get_many_abstracts_cycling_apis_success(
    crossref_api_config_valid_batch, scopus_api_config_valid_batch
):
    settings = get_settings()
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config(
            [crossref_api_config_valid_batch, scopus_api_config_valid_batch], settings
        )
    )
    test_doi_list = ["10.1000/xyz123", "10.1000/xyz124", "10.1000/xyz125"]
    test_abstract_list = ["abstract text 1", "abstract text 2", "abstract text 3"]
    test_response_objects = [
        [{"doi": doi, "abstract": abstract}]
        for doi, abstract in zip(test_doi_list, test_abstract_list, strict=False)
    ]
    with patch.object(
        fetcher, "fetch_many_abstracts", return_value=(x for x in test_response_objects)
    ):
        result = fetcher.get_many_abstracts_cycling_apis(
            ["10.1000/xyz123", "10.1000/xyz124", "10.1000/xyz125"]
        )
        assert result == [item for sublist in test_response_objects for item in sublist]


def test_get_many_abstracts_cycling_apis_not_found(
    crossref_api_config_valid_batch, scopus_api_config_valid_batch
):
    settings = get_settings()
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config(
            [crossref_api_config_valid_batch, scopus_api_config_valid_batch], settings
        )
    )
    with (
        patch.object(fetcher, "fetch_many_abstracts", return_value=None),
        pytest.raises(AbstractNotFoundError),
    ):
        fetcher.get_many_abstracts_cycling_apis(["10.1000/xyz123"])
