"""Define config for PubMed API DOI lookup and abstract retrieval."""

from pydantic import HttpUrl

from far.config import Settings
from far.data_models.generic import AbstractUnpackStrategy, APIConfig
from far.providers.pubmed import fetch_abstract_by_doi


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

    pubmed_search_url = HttpUrl(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    )
    return APIConfig(
        name="pubmed_batch",
        url=pubmed_search_url,
        require_api_key=False,
        api_key_env_var_name=None,
        api_key_placement=None,
        query_params=query_params,
        unpack_strategy=AbstractUnpackStrategy(
            source="pubmed_batch",
            strategy=["unused"],
        ),
        provider_fetch_hook=fetch_abstract_by_doi,
    )
