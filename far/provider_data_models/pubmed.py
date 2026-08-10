"""Define config for PubMed API DOI lookup and abstract retrieval."""

from pydantic import HttpUrl

from far.config import Settings
from far.fetching.pubmed import fetch_abstract_by_doi
from far.provider_data_models.generic import (
    AbstractUnpackStrategy,
    APIConfig,
    ExternalAPI,
)

PUBMED_SEARCH_URL = HttpUrl(
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
)


def get_pubmed_batch_api_config(settings: Settings) -> APIConfig:
    """
    Define and return the PubMed API configuration.

    Returns:
        APIConfig: An instance of APIConfig with the PubMed API settings.

    """
    query_params: dict[str, str] = {
        "db": "pubmed",
        "retmode": "json",
    }
    query_params["tool"] = settings.robot_title
    if settings.mailto:
        query_params["email"] = str(settings.mailto)

    return APIConfig(
        name=ExternalAPI.PUBMED,
        url=PUBMED_SEARCH_URL,
        require_api_key=False,
        api_key_env_var_name=None,
        api_key_placement=None,
        query_params=query_params,
        unpack_strategy=AbstractUnpackStrategy(
            source=ExternalAPI.PUBMED,
            strategy=["unused"],
        ),
        provider_fetch_hook=fetch_abstract_by_doi,
    )
