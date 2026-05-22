"""Define a local configuration for running the fetch-abstracts-robot."""

import sys

from loguru import logger

from far.config import Settings
from far.data_models.crossref import get_crossref_batch_api_config
from far.data_models.generic import APIConfig, ExternalAPI
from far.data_models.scopus import get_scopus_batch_api_config
from far.enhancement_processor import AbstractEnhancementProcessor
from far.fetch_abstract import prepare_api_config


def set_up_processor(
    settings: Settings, excluded_apis: list[ExternalAPI] | None
) -> AbstractEnhancementProcessor:
    """
    Set up the AbstractEnhancementProcessor with API configurations.

    Args:
        settings (Settings): The application settings.
        excluded_apis (list[ExternalAPI] | None): A list of APIs to exclude.

    Returns:
        AbstractEnhancementProcessor: An instance of the abstract processor.

    """
    excluded_api_names = (
        [api.name.lower() for api in excluded_apis] if excluded_apis else []
    )
    available_api_configs: list[APIConfig] = [
        config
        for name, config in [
            ("crossref", get_crossref_batch_api_config(settings)),
            ("scopus", get_scopus_batch_api_config()),
        ]
        if excluded_api_names is None
        or not any(
            name.lower() in excluded_api_name
            for excluded_api_name in excluded_api_names
        )
    ]
    if len(available_api_configs) == 0:
        logger.critical(
            "No APIs available after applying exclusions: {}", excluded_apis
        )
        sys.exit(1)

    logger.info(
        "Available APIs after applying exclusions: {}",
        [config.name for config in available_api_configs],
    )

    global_api_config = prepare_api_config(
        api_configs=available_api_configs, settings=settings
    )

    title = "Local Abstract Fetcher"

    return AbstractEnhancementProcessor(
        robot_version="local",
        source_name=title,
        global_api_config=global_api_config,
        available_api_configs=available_api_configs,
    )
