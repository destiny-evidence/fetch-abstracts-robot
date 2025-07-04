"""tests for generic data models in app/data_models/generic.py."""

import pytest
from pydantic import AnyUrl, ValidationError

from app.config import get_settings
from app.data_models import generic

# @pytest.fixture
# def scopus_config():
#     api_config = generic.APIConfig(
#         name=generic.ExternalAPI.SCOPUS,
#         url="https://api.example.com",
#         require_api_key=True,
#         api_key_env_var_name="scopus_api_key",
#         api_key_placement="X-API-Key",
#         query_params={},
#         headers={"X-API-Key": ""},
#         unpack_strategy=generic.AbstractUnpackStrategy(
#             source=generic.ExternalAPI.SCOPUS, strategy=["data", "abstract"]
#         ),
#     )


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


def test_api_config_validator_success():
    # api_config = generic.APIConfig(
    #     name=generic.ExternalAPI.SCOPUS,
    #     url="https://api.example.com",
    #     require_api_key=True,
    #     api_key_env_var_name="scopus_api_key",
    #     api_key_placement="X-API-Key",
    #     query_params={},
    #     headers={"X-API-Key": ""},
    #     unpack_strategy=generic.AbstractUnpackStrategy(
    #         source=generic.ExternalAPI.SCOPUS, strategy=["data", "abstract"]
    #     ),
    # )
    assert api_config.headers == {"X-API-Key": ""}
    assert api_config.name == generic.ExternalAPI.SCOPUS
    assert api_config.url == AnyUrl("https://api.example.com")
    assert api_config.query_params == {}
    assert (
        api_config.unpack_strategy.model_dump()["source"] == generic.ExternalAPI.SCOPUS
    )
    assert api_config.unpack_strategy.model_dump()["strategy"] == ["data", "abstract"]


def test_api_config_validator_failure():
    with pytest.raises(ValidationError):
        generic.APIConfig(
            name=generic.ExternalAPI.SCOPUS,
            url="https://api.example.com",
            api_key_env_var_name="scopus_api_key",
            api_key_placement="X-API-Key",
            query_params={},
            headers=None,  # missing key
            unpack_strategy="abstract",  # invalid unpack strategy
        )


def test_api_config_init_api_key_success():
    config = generic.APIConfig(
        name=generic.ExternalAPI.SCOPUS,
        url="https://api.example.com",
        api_key_env_var_name="elsevier_scopus_key",
        api_key_placement="X-API-Key",
        query_params={},
        headers={"X-API-Key": ""},
        unpack_strategy=generic.AbstractUnpackStrategy(
            source=generic.ExternalAPI.SCOPUS, strategy=["data", "abstract"]
        ),
    )
    settings = get_settings()
    config.init_api_key(settings)
    assert config.headers["X-API-Key"] == "dummy_scopus_key"


def test_api_config_init_api_key_missing():
    config = generic.APIConfig(
        name=generic.ExternalAPI.SCOPUS,
        url="https://api.example.com",
        api_key_env_var_name="missing_api_key",
        api_key_placement="X-API-Key",
        query_params={},
        headers={"X-API-Key": ""},
        unpack_strategy=generic.AbstractUnpackStrategy(
            source=generic.ExternalAPI.SCOPUS, strategy=["data", "abstract"]
        ),
    )
    settings = get_settings()
    with pytest.raises(generic.APIKeyNotPresentError):
        config.init_api_key(settings)


def test_api_config_populate_query():
    api_config = generic.APIConfig(
        name=generic.ExternalAPI.SCOPUS,
        url="https://api.example.com",
        api_key_env_var_name="scopus_api_key",
        api_key_placement="X-API-Key",
        query_params={},
        headers={"X-API-Key": ""},
        unpack_strategy=generic.AbstractUnpackStrategy(
            source=generic.ExternalAPI.SCOPUS, strategy=["data", "abstract"]
        ),
    )
    url = api_config.populate_query("test_query")
    assert url == f"{api_config.url}{"test_query"}"
    assert url == f"{api_config.url}{"test_query"}"
