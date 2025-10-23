"""customisations on the loguru logger."""

import sys

from loguru import logger

from app.config import Environment, get_settings

settings = get_settings()

logger.remove(0)

if settings.env in {Environment.PRODUCTION, Environment.STAGING}:
    logger.add(sys.stderr, level="INFO")

else:
    logger.add("app.log", level="DEBUG", rotation="500 mb")
    logger.add(sys.stderr, level="DEBUG")
