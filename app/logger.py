"""customisations on the loguru logger."""

import sys

import loguru
from loguru import logger

from app.config import Environment, get_settings


def set_up_logger() -> loguru._logger.Logger:
    """
    Set up the logger based on the application settings.

    Args:
            settings (Settings): The application settings.

    Returns:
            Logger: Configured loguru logger instance.

    """
    settings = get_settings()
    logger.remove(0)

    if settings.env in {Environment.PRODUCTION, Environment.STAGING}:
        logger.add(sys.stderr, level="INFO")

    else:
        logger.add("app.log", level="DEBUG", rotation="500 mb")
        logger.add(sys.stderr, level="DEBUG")

    return logger


__all__ = ["logger"]
