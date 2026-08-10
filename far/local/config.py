"""Define a local configuration for running the fetch-abstracts-robot."""

import sys

from loguru import logger

from far.config import Settings
from far.enhancements.processor import (
    AbstractEnhancementProcessor,
    create_enhancement_processor,
)
from far.provider_data_models.generic import ExternalAPI


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
    title = "Local Abstract Fetcher"
    try:
        return create_enhancement_processor(
            settings,
            robot_version="local",
            source_name=title,
            excluded_apis=excluded_apis,
        )
    except ValueError:
        logger.critical(
            "No APIs available after applying exclusions: {}", excluded_apis
        )
        sys.exit(1)
