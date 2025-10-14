"""Main module for the Fetch Abstracts Robot."""

import asyncio
import contextlib
import signal
import sys
from types import FrameType
from typing import Final

from destiny_sdk.client import Client as DestinyClient
from destiny_sdk.robots import (
    RobotEnhancementBatch,
    RobotEnhancementBatchResult,
    RobotError,
)
from enhancement_processor import AbstractEnhancementProcessor
from loguru import logger

from app.auth import auth_strategy_robot
from app.config import get_settings
from app.data_models.crossref import get_crossref_batch_api_config
from app.data_models.scopus import get_scopus_batch_api_config
from app.fetch_abstract import prepare_api_config
from app.utils import get_version_number

settings = get_settings()
abstract_collector_auth = auth_strategy_robot(settings=settings)

TITLE: Final[str] = settings.robot_title

client = DestinyClient(
    base_url=settings.destiny_repository_url,
    client_id=settings.robot_id,
    secret_key=settings.robot_secret,
)

# configurations for all APIs we can hit to get abstracts
AVAILABLE_API_CONFIGS = [
    get_crossref_batch_api_config(settings),
    get_scopus_batch_api_config(),
]
global_api_config = prepare_api_config(
    api_configs=AVAILABLE_API_CONFIGS, settings=settings
)

processor = AbstractEnhancementProcessor(
    robot_version=get_version_number(),
    source_name=TITLE,
    global_api_config=global_api_config,
    available_api_configs=AVAILABLE_API_CONFIGS,
)


async def process_robot_enhancement_batch(batch: RobotEnhancementBatch) -> None:
    """
    Process a robot enhancement batch by creating abstract enhancements.

    Args:
        batch (RobotEnhancementBatch): The batch of enhancements to process.

    """
    try:
        await processor.process_batch(batch)
        client.send_robot_enhancement_batch_result(
            RobotEnhancementBatchResult(request_id=batch.id)
        )

        logger.info("Successfull processed robot enhancement batch %s", batch.id)

    except Exception:
        logger.exception("Error processing robot enhancement batch %s", batch.id)

        client.send_robot_enhancement_batch_result(
            RobotEnhancementBatchResult(
                request_id=batch.id,
                error=RobotError(
                    message=(
                        "Failed to process request:"
                        " {robot_enhancement_batch_process_error!s}"
                    ),
                ),
            )
        )
        raise


async def poll_for_batches() -> None:
    """Poll for new robot enhancement batches and process them."""
    logger.info("Starting to poll for robot enhancement batches...")

    while True:
        try:
            batch = client.poll_robot_enhancement_batch(
                robot_id=settings.robot_id, limit=settings.batch_size
            )

            if batch is None:
                logger.debug("No batches available")
                await asyncio.sleep(settings.poll_interval_seconds)
                continue

            logger.info("Found batch %s to process", batch.id)

            try:
                await process_robot_enhancement_batch(batch)

            except Exception as process_batch_error:  # noqa: BLE001
                logger.exception(
                    "Error processing batch %s: %s", batch.id, process_batch_error
                )
        except Exception as poll_error:  # noqa: BLE001
            logger.exception("Error polling for batches: %s", poll_error)
        await asyncio.sleep(settings.poll_interval_seconds)


shutdown_event = asyncio.Event()


def signal_handler(signum: int, _frame: FrameType | None) -> None:
    """Handle termination signals to gracefully shut down the application."""
    logger.info("Received signal %s, initiating graceful shutdown...", signum)
    shutdown_event.set()


async def main() -> None:
    """Run the polling robot."""
    logger.info("Starting %s polling loop", TITLE)
    logger.info("Polling interval: %d seconds", settings.poll_interval_seconds)
    logger.info("Batch size: %d", settings.batch_size)

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        poll_task = asyncio.create_task(poll_for_batches())

        # Wait for either the polling task to complete or a shutdown signal
        _done, pending = await asyncio.wait(
            [poll_task, asyncio.create_task(shutdown_event.wait())],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Cancel remaining tasks

        for task in pending:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        logger.info("Shutdown complete.")

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
        sys.exit(0)

    except Exception:  # noqa: BLE001
        logger.exception("Unexpected fatal error occurred:")
        sys.exit(1)
