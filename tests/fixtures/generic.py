import pytest

from far.provider_data_models.generic import (
    AbstractUnpackStrategy,
    APIConfig,
    ExternalAPI,
    ExternalAPIPriority,
    QueryType,
)


@pytest.fixture
def external_api_priorities() -> dict[str, ExternalAPIPriority]:
    """
    Fixture to provide the external API priority configuration.

    Returns:
        dict[str, ExternalAPIPriority]:
            Dictionary of the configured external API priorities.

    """
    return {
        "batch": ExternalAPIPriority(
            name="batch",
            priorities={
                ExternalAPI.CROSSREF_BATCH: 1,
                ExternalAPI.PUBMED_BATCH: 2,
                ExternalAPI.SCOPUS_BATCH: 3,
            },
        ),
    }


@pytest.fixture
def invalid_api_config() -> APIConfig:
    """
    Provide an invalid API configuration.

    Returns:
        APIConfig: An APIConfig instance with invalid settings.

    """
    return APIConfig(
        name=ExternalAPI.SCOPUS_BATCH,
        url="http://fake-api.com",
        require_api_key=True,
        api_key_env_var_name="FAKE_API_KEY",  # pragma: allowlist secret
        api_key_placement="api_key_placement",  # pragma: allowlist secret
        query_type=QueryType.BATCHED_SINGLE,
        query_params={"param1": "value1"},
        headers={"Authorization": "Bearer fake_token", "api_key_placement": ""},
        unpack_strategy=AbstractUnpackStrategy(
            source=ExternalAPI.SCOPUS_BATCH,
            strategy=["data", "abstract"],
        ),
    )
