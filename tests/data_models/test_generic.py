"""tests for generic data models in app/data_models/generic.py."""

import pytest
from pydantic import ValidationError

from far.config import get_settings
from far.data_models.generic import (
    AbstractNotFoundError,
    AbstractUnpackError,
    AbstractUnpackStrategy,
    APIConfig,
    APIKeyNotPresentError,
    ExternalAPI,
    ExternalAPIPriority,
)


def test_custom_exceptions():
    error_msg = "API key missing"
    with pytest.raises(APIKeyNotPresentError):
        raise APIKeyNotPresentError(error_msg)
    error_msg = "Unpack failed"
    with pytest.raises(AbstractUnpackError):
        raise AbstractUnpackError(error_msg)
    error_msg = "Not found"
    with pytest.raises(AbstractNotFoundError):
        raise AbstractNotFoundError(error_msg)


def test_external_api_enum():
    assert ExternalAPI.SCOPUS_BATCH == "scopus_batch"
    assert ExternalAPI.CROSSREF_BATCH == "crossref_batch"
    assert set(ExternalAPI) == {
        ExternalAPI.CROSSREF_BATCH,
        ExternalAPI.SCOPUS_BATCH,
    }


def test_external_api_priority_model():
    model = ExternalAPIPriority(
        name="test_priority",
        priorities={
            ExternalAPI.CROSSREF_BATCH: 1,
            ExternalAPI.SCOPUS_BATCH: 2,
        },
    )
    assert model.priorities[ExternalAPI.CROSSREF_BATCH] == 1
    assert model.priorities[ExternalAPI.SCOPUS_BATCH] == 2


def test_abstract_unpack_strategy_():
    my_strategy = AbstractUnpackStrategy(
        source=ExternalAPI.SCOPUS_BATCH, strategy=["abstracts", "abstractText"]
    )
    assert my_strategy.source == ExternalAPI.SCOPUS_BATCH
    assert my_strategy.strategy == ["abstracts", "abstractText"]


@pytest.mark.parametrize(
    (
        "api_config_fixture",
        "expected_headers",
        "expected_name",
        "expected_url",
        "expected_query_params",
        "expected_unpack_source",
        "expected_unpack_strategy",
    ),
    [
        (
            "scopus_api_config_valid_batch",
            {"X-API-Key": ""},
            ExternalAPI.SCOPUS_BATCH,
            "https://api.example.com/",
            {},
            ExternalAPI.SCOPUS_BATCH,
            ["search-results", "entry", "dc:description"],
        ),
        (
            "crossref_api_config_valid_batch",
            {"Accept": "application/json"},
            ExternalAPI.CROSSREF_BATCH,
            "https://api.example.com/",
            {},
            ExternalAPI.CROSSREF_BATCH,
            ["message", "abstract"],
        ),
    ],
)
def test_api_config_validator_success(
    request,
    api_config_fixture,
    expected_headers,
    expected_name,
    expected_url,
    expected_query_params,
    expected_unpack_source,
    expected_unpack_strategy,
):
    api_config = request.getfixturevalue(api_config_fixture)
    assert api_config.headers == expected_headers
    assert api_config.name == expected_name
    assert str(api_config.url) == expected_url
    assert api_config.query_params == expected_query_params
    assert api_config.unpack_strategy.source == expected_unpack_source
    assert api_config.unpack_strategy.strategy == expected_unpack_strategy


@pytest.mark.parametrize(
    ("api_config_fixture"),
    [
        ("scopus_api_config_valid_batch"),
        ("crossref_api_config_valid_batch"),
    ],
)
def test_api_config_validator_failure(request, api_config_fixture, monkeypatch):
    api_config = request.getfixturevalue(api_config_fixture)
    bad_fields = [
        ("headers", None),
        ("unpack_strategy", "not_a_strategy"),
        ("name", "not_an_enum"),
    ]
    for field, bad_value in bad_fields:
        broken = api_config.model_copy()
        setattr(broken, field, bad_value)
        with pytest.raises(ValidationError):
            APIConfig.model_validate(broken.__dict__)


@pytest.mark.parametrize(
    ("api_config_fixture", "expected_key", "expected_value"),
    [
        ("scopus_api_config_valid_batch", "X-API-Key", "dummy_scopus_key"),
        ("crossref_api_config_valid_batch", None, None),
    ],
)
def test_api_config_init_api_key_success(
    request, api_config_fixture, expected_key, expected_value, test_settings
):
    api_config = request.getfixturevalue(api_config_fixture)

    api_config.init_api_key(test_settings)
    if expected_key:
        assert api_config.headers[expected_key] == expected_value
    else:
        # For APIs that do not require a key, headers should remain unchanged
        assert "Accept" in api_config.headers or api_config.headers == {}


def test_api_config_init_api_key_missing(invalid_api_config):
    settings = get_settings()
    with pytest.raises(APIKeyNotPresentError):
        invalid_api_config.init_api_key(settings)


@pytest.mark.parametrize(
    ("api_config_fixture", "query"),
    [
        ("scopus_api_config_valid_batch", ["test_DOI_1", "test_doi_2", "test_doi_3"]),
    ],
)
def test_api_config_populate_query_batch(request, api_config_fixture, query):
    api_config = request.getfixturevalue(api_config_fixture)
    expected_query = " OR ".join([f"DOI({q})" for q in query])
    request_params = api_config.populate_query(query)
    # This assumes populate_query appends the query string to the base URL
    assert request_params["query_params"]["query"] == expected_query
    assert str(request_params["url"]) == f"{api_config.url}"


@pytest.mark.parametrize(
    ("api_config_fixture", "query"),
    [
        ("crossref_api_config_valid_batch", ["test_DOI"]),
    ],
)
def test_api_config_populate_query_batched_single(request, api_config_fixture, query):
    api_config = request.getfixturevalue(api_config_fixture)
    expected_extracted_query = query[0]
    url = api_config.populate_query(query)["url"]
    # This assumes populate_query appends the query string to the base URL
    assert url == f"{api_config.url}{expected_extracted_query}"
