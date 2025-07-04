"""tests for generic data models in app/data_models/generic.py."""

import pytest
from pydantic import AnyUrl, ValidationError

from app.config import get_settings
from app.data_models import generic


def test_custom_exceptions():
    error_msg = "API key missing"
    with pytest.raises(generic.APIKeyNotPresentError):
        raise generic.APIKeyNotPresentError(error_msg)
    error_msg = "Unpack failed"
    with pytest.raises(generic.AbstractUnpackError):
        raise generic.AbstractUnpackError(error_msg)
    error_msg = "Not found"
    with pytest.raises(generic.AbstractNotFoundError):
        raise generic.AbstractNotFoundError(error_msg)


def test_external_api_enum():
    assert generic.ExternalAPI.SCOPUS == "scopus"
    assert generic.ExternalAPI.WEB_OF_SCIENCE == "web_of_science"
    assert generic.ExternalAPI.CROSSREF == "crossref"
    assert set(generic.ExternalAPI) == {
        generic.ExternalAPI.SCOPUS,
        generic.ExternalAPI.WEB_OF_SCIENCE,
        generic.ExternalAPI.CROSSREF,
    }


def test_external_api_priority_model():
    model = generic.ExternalAPIPriority(
        priorities={
            generic.ExternalAPI.CROSSREF: 1,
            generic.ExternalAPI.SCOPUS: 2,
            generic.ExternalAPI.WEB_OF_SCIENCE: 3,
        }
    )
    assert model.priorities[generic.ExternalAPI.CROSSREF] == 1
    assert model.priorities[generic.ExternalAPI.SCOPUS] == 2
    assert model.priorities[generic.ExternalAPI.WEB_OF_SCIENCE] == 3


def test_abstract_unpack_strategy_():
    my_strategy = generic.AbstractUnpackStrategy(
        source=generic.ExternalAPI.SCOPUS, strategy=["abstracts", "abstractText"]
    )
    assert my_strategy.source == generic.ExternalAPI.SCOPUS
    assert my_strategy.strategy == ["abstracts", "abstractText"]


@pytest.mark.parametrize(
    "api_config_fixture,expected_headers,expected_name,expected_url,expected_query_params,expected_unpack_source,expected_unpack_strategy",
    [
        (
            "scopus_api_config_valid",
            {"X-API-Key": ""},
            generic.ExternalAPI.SCOPUS,
            "https://api.example.com/",
            {},
            generic.ExternalAPI.SCOPUS,
            ["data", "abstract"],
        ),
        # commenting out WOS as it's currently
        # invalid due to not having an api key
        # (
        #     "wos_api_config_valid",
        #     {"wos_key": ""},
        #     generic.ExternalAPI.WEB_OF_SCIENCE,
        #     "https://api.example.com/",
        #     {},
        #     generic.ExternalAPI.WEB_OF_SCIENCE,
        #     ["text", "meta", "abstract"],
        # ),
        (
            "crossref_api_config_valid",
            {"Accept": "application/json"},
            generic.ExternalAPI.CROSSREF,
            "https://api.example.com/",
            {},
            generic.ExternalAPI.CROSSREF,
            ["text", "meta", "abstract"],
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


def test_api_config_validator_failure(scopus_api_config_valid, monkeypatch):
    bad_fields = [
        ("headers", None),
        ("unpack_strategy", "not_a_strategy"),
        ("name", "not_an_enum"),
    ]
    for field, bad_value in bad_fields:
        broken = scopus_api_config_valid.model_copy()
        setattr(broken, field, bad_value)
        with pytest.raises(ValidationError):
            generic.APIConfig.model_validate(broken.__dict__)


@pytest.mark.parametrize(
    "api_config_fixture,expected_key,expected_value",
    [
        # SCOPUS: requires API key, key present
        ("scopus_api_config_valid", "X-API-Key", "dummy_scopus_key"),
        # CROSSREF: does not require API key
        ("crossref_api_config_valid", None, None),
    ],
)
def test_api_config_init_api_key_success(
    request, api_config_fixture, expected_key, expected_value, monkeypatch
):
    api_config = request.getfixturevalue(api_config_fixture)
    settings = get_settings()

    api_config.init_api_key(settings)
    if expected_key:
        assert api_config.headers[expected_key] == expected_value
    else:
        # For APIs that do not require a key, headers should remain unchanged
        assert "Accept" in api_config.headers or api_config.headers == {}


def test_api_config_init_api_key_missing(wos_api_config_invalid):
    settings = get_settings()
    with pytest.raises(generic.APIKeyNotPresentError):
        wos_api_config_invalid.init_api_key(settings)


@pytest.mark.parametrize(
    "api_config_fixture",
    [
        "scopus_api_config_valid",
        "crossref_api_config_valid",
        # Add "wos_api_config_valid" if/when available and valid
    ],
)
def test_api_config_populate_query(request, api_config_fixture):
    api_config = request.getfixturevalue(api_config_fixture)
    query = "test_query"
    url = api_config.populate_query(query)
    # This assumes populate_query appends the query string to the base URL
    assert url
