"""Generation functions for single and batch abstract enhancements."""

import uuid

import httpx
from destiny_sdk.enhancements import (
    AbstractContentEnhancement,
    AbstractProcessType,
    Enhancement,
)
from destiny_sdk.references import Reference
from destiny_sdk.robots import (
    LinkedRobotError,
)
from destiny_sdk.visibility import Visibility
from loguru import logger

from app.data_models.generic import AbstractNotFoundError, APIConfig
from app.fetch_abstract import AbstractFetcher
from app.utils import get_doi_from_reference, get_version_number


class BatchEnhancementGenerationError(Exception):
    """Custom exception for errors during batch enhancement generation."""


def generate_abstract_enhancement_single_request(
    abstract_fetcher: AbstractFetcher,
    reference: Reference,
    app_title: str = "Fetch Abstracts Robot (FAR)",
) -> Enhancement:
    """
    Generate an abstract enhancement for a single reference.

    Args:
        abstract_fetcher (AbstractFetcher): The abstract fetcher instance.
        reference (Reference): The reference object containing metadata.
        app_title (str): The title of the application.

    Returns:
        Enhancement: The generated abstract enhancement.

    Raises:
        AbstractNotFoundError: If no abstract is found for the given reference.
        httpx.HTTPError: If there is an HTTP error during the API call.

    """
    doi = get_doi_from_reference(reference=reference)
    try:
        enhancement_dict = abstract_fetcher.get_one_abstract_cycling_apis(doi=doi)
        abstract = enhancement_dict.get("abstract", None)
    except AbstractNotFoundError:
        logger.error(f"Abstract not found for DOI: {doi}")
        raise
    except httpx.HTTPError as http_error:
        logger.error(f"HTTP error occurred: {http_error}")
        raise
    return Enhancement(
        reference_id=reference.id,
        source=app_title,
        visibility=Visibility.PUBLIC,
        robot_version=get_version_number(),
        content_version=f"{uuid.uuid4()}",
        content=AbstractContentEnhancement(
            process=AbstractProcessType.CLOSED_API,
            abstract=abstract,
        ),
    )


def generate_abstract_enhancement_batch_request(
    references: list[Reference],
    enhancements_references_map: list[dict],
    available_api_configs: list[APIConfig],
    app_title: str = "Fetch Abstracts Robot (FAR)",
) -> bytes:
    """
    Generate a batch of abstract enhancements from a batch of references.

    Args:
        references (list[Reference]): A list of reference objects.
        enhancements_references_map (list[dict]): A list of enhancement dictionaries
            that map reference IDs to their enhancements.

    Returns:
        bytes: The generated batch of enhancements in JSONL format.

    Raises:
        BatchEnhancementGenerationError: If there is an error generating the batch.
            Represents a complete failing of the enhancement process.

    """
    file_content = b""
    version_number = get_version_number()
    enhancements_by_id = {
        enhancement["id"]: enhancement for enhancement in enhancements_references_map
    }
    successful_enhancements = 0
    for reference in references:
        enhancement = enhancements_by_id.get(reference.id)
        if not enhancement:
            error_message = f"Enhancement generation error for {reference.id}."
            logger.error(error_message)
            raise BatchEnhancementGenerationError(error_message)
        abstract = enhancement.get("abstract", None)
        if not abstract:
            sources = [
                config.name.value
                for config in available_api_configs
                if "_" not in config.name.value
            ]
            error_message = f"No abstract found in {sources}"
            logger.warning(error_message)
            # Confirmed by Jack that we should be writing a LinkedRobotError
            # (see https://destiny-evidence.github.io/destiny-repository/sdk/schemas.html#libs.sdk.src.destiny_sdk.robots.LinkedRobotError)
            # for the references that fail
            linked_robot_error = LinkedRobotError(
                message=error_message,
                reference_id=reference.id,
            )
            file_content += (linked_robot_error.to_jsonl() + "\n").encode("utf-8")
            continue
        enhancement_source = enhancement.get("source", app_title)
        if not enhancement_source:
            enhancement_source_short = "UNKNOWN"
        if enhancement_source:
            enhancement_source_short = enhancement_source.split("_")[0].upper()
        visibility_level = (
            Visibility.PUBLIC
            if enhancement_source_short == "CROSSREF"
            else Visibility.RESTRICTED
        )

        file_content += (
            Enhancement(
                reference_id=reference.id,
                source=app_title,
                visibility=visibility_level,
                robot_version=version_number,
                content_version=f"{uuid.uuid4()}",
                content=AbstractContentEnhancement(
                    process=AbstractProcessType.CLOSED_API,
                    abstract=enhancement["abstract"],
                ),
            ).to_jsonl()
            + "\n"
        ).encode("utf-8")
        successful_enhancements += 1
    if successful_enhancements == 0:
        reference_ids_attempted = ", ".join([ref.id for ref in references])
        error_message = (
            "No successful enhancements generated for reference"
            f" IDs {reference_ids_attempted}"
        )
        logger.error(error_message)
        raise BatchEnhancementGenerationError(error_message)
    return file_content
