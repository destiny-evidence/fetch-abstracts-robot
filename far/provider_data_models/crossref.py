"""Config constants for CrossRef API; single & batch."""

from far.config import Settings
from far.provider_data_models.generic import (
    AbstractUnpackStrategy,
    APIConfig,
    ExternalAPI,
    QueryType,
)


def get_crossref_batch_api_config(settings: Settings) -> APIConfig:
    """
    Define and return the CrossRef batch API configuration.

    Args:
        settings (Settings): The application settings containing configuration values.

    Returns:
        APIConfig: The configuration for the CrossRef batch API.

    """
    crossref_url = "https://api.crossref.org/works/"
    crossref_query_params = {"mailto": settings.mailto}  # type: dict
    crossref_headers = {
        "User-Agent": "destiny-project-ucl",
        "Accept": "application/json",
    }
    crossref_unpack_strategy = AbstractUnpackStrategy(
        source=ExternalAPI.CROSSREF,
        clean_abstract_string=True,
        strategy=["message", "abstract"],
    )

    return APIConfig(
        name=ExternalAPI.CROSSREF,
        url=crossref_url,
        require_api_key=False,
        api_key_env_var_name=None,
        api_key_placement=None,
        headers=crossref_headers,
        query_type=QueryType.BATCHED_SINGLE,
        query_params=crossref_query_params,
        unpack_strategy=crossref_unpack_strategy,
    )
