"""Define provider-specific data models for the application."""

from far.config import Settings
from far.provider_data_models.crossref import get_crossref_batch_api_config
from far.provider_data_models.generic import APIConfig
from far.provider_data_models.pubmed import get_pubmed_batch_api_config
from far.provider_data_models.scopus import get_scopus_batch_api_config


def get_all_provider_api_configs(settings: Settings) -> list[APIConfig]:
    """
    Return a list of all provider API configuration instances.

    Args:
        settings (Settings): The application settings.

    Returns:
        list[APIConfig]: A list of provider API configuration instances.

    """
    return [
        get_crossref_batch_api_config(settings),
        get_pubmed_batch_api_config(settings),
        get_scopus_batch_api_config(),
    ]
