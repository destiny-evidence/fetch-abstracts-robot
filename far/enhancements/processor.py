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
    RobotEnhancementBatch,
)
from destiny_sdk.visibility import Visibility
from loguru import logger

from far.fetch_abstract import AbstractFetcher
from far.provider_data_models.generic import APIConfig
from far.utils import get_doi_from_reference, get_version_number, normalise_doi


class BatchEnhancementGenerationError(Exception):
    """Custom exception for errors during batch enhancement generation."""


class FullBatchFailureError(Exception):
    """Custom exception for complete failure of batch processing."""


class AbstractEnhancementProcessor:
    """Handles the processing of abstract enhancement requests."""

    def __init__(
        self,
        robot_version: str,
        source_name: str,
        global_api_config: dict[str, APIConfig],
        available_api_configs: list[APIConfig],
    ) -> None:
        """
        Initialize the processor with configuration.

        Args:
            robot_version (str): The version of the robot.
            source_name (str): The name of the `source` in the destiny repository.
                In practical terms, this is the app name _of this app_.
            global_api_config (dict[str, APIConfig]): Global API configuration.
            available_api_configs (list[APIConfig]): List of API configurations.

        """
        self.robot_version = robot_version
        self.source_name = source_name

        self.abstract_fetcher = AbstractFetcher(global_api_config)
        self.available_api_configs = available_api_configs

    def create_abstract_enhancement(
        self,
        references: list[Reference],
    ) -> list[Enhancement]:
        """
        Create abstract enhancements with efficient memory usage.

        This operates on a batch of references as a default,
        but that could be a batch of one.

        This leverages the `get_many_abstracts_cycling_apis` method,
        rather than strictly looping over individual requests (although
        this may be done in the background, depending on API config).

        Args:
            references (list[Reference]): A list of reference objects.

        Returns:
            list[Enhancement]: The generated batch of enhancements.

        """
        logger.debug(f"References passed in: {references}")
        dois = [get_doi_from_reference(ref) for ref in references]
        logger.debug(f"DOIs extracted: {dois}")
        abstracts_dois_dict = self.abstract_fetcher.get_many_abstracts_cycling_apis(
            dois
        )

        # Pre-normalise once per reference (O(n)) and once per abstract entry (O(m))
        # to avoid O(n*m) validate_doi calls inside the nested comprehension.
        ref_normalised_dois = {
            ref.id: doi
            for ref in references
            if (doi := normalise_doi(get_doi_from_reference(ref))) is not None
        }
        normalised_abstracts_map = {
            key: entry
            for entry in abstracts_dois_dict
            if (key := normalise_doi(entry.get("doi", ""))) is not None
        }

        enhancement_reference_map = [
            {
                "id": ref.id,
                "doi": matched.get("doi"),
                "abstract": matched.get("abstract"),
            }
            for ref in references
            if (ref_doi := ref_normalised_dois.get(ref.id)) is not None
            and (matched := normalised_abstracts_map.get(ref_doi)) is not None
        ]

        try:
            abstract_enhancements = self.generate_abstract_enhancement_batch_request(
                references=references,
                enhancements_references_map=enhancement_reference_map,
                available_api_configs=self.available_api_configs,
                app_title=self.source_name,
            )
        except BatchEnhancementGenerationError as batch_error:
            error_message = (
                f"Error during generation of enhancement request: {batch_error}."
                " Failing entire request."
            )
            logger.error(error_message)
            raise batch_error from batch_error
        return abstract_enhancements

    def generate_abstract_enhancement_batch_request(
        self,
        references: list[Reference],
        enhancements_references_map: list[dict],
        available_api_configs: list[APIConfig],
        app_title: str,
    ) -> list[Enhancement | LinkedRobotError]:
        """
        Generate a batch of abstract enhancements from a batch of references.

        Args:
            references (list[Reference]): A list of reference objects.
            enhancements_references_map (list[dict]): A list of enhancement dictionaries
                that map reference IDs to their enhancements.

        Returns:
            list[Enhancement]: The generated batch of enhancements.

        Raises:
            BatchEnhancementGenerationError: If there is an error generating the batch.
                Represents a complete failing of the enhancement process.

        """
        enhancements_out = []
        version_number = get_version_number()
        enhancements_by_id = {
            enhancement["id"]: enhancement
            for enhancement in enhancements_references_map
        }
        successful_enhancements = 0
        for reference in references:
            enhancement = enhancements_by_id.get(reference.id)
            if not enhancement:
                error_message = (
                    f"Enhancement generation error for {reference.id}."
                    " Reference ID is missing in the enhancements map."
                )
                logger.error(error_message)
                raise BatchEnhancementGenerationError(error_message)
            abstract = enhancement.get("abstract", None)
            if not abstract:
                sources = {
                    config.name.value.split("_")[0].upper()
                    for config in available_api_configs
                }
                error_message = f"No abstract found in {sources}"
                logger.warning(error_message)
                # Confirmed by Jack that we should be writing a LinkedRobotError
                # (see https://destiny-evidence.github.io/destiny-repository/sdk/schemas.html#libs.sdk.src.destiny_sdk.robots.LinkedRobotError)
                # for the references that fail
                linked_robot_error = LinkedRobotError(
                    message=error_message,
                    reference_id=reference.id,
                )
                enhancements_out.append(linked_robot_error)
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

            enhancements_out.append(
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
                )
            )

            successful_enhancements += 1
        if successful_enhancements == 0:
            reference_ids_attempted = ", ".join([str(ref.id) for ref in references])
            error_message = (
                "No successful enhancements generated for reference"
                f" IDs {reference_ids_attempted}"
            )
            logger.error(error_message)
            raise BatchEnhancementGenerationError(error_message)
        return enhancements_out

    async def download_references(self, reference_storage_url: str) -> list[Reference]:
        """
        Download references from a given URL.

        Args:
            reference_storage_url (str): The URL to download references from.

        Returns:
            list[Reference]: A list of Reference objects.

        """
        references = []
        async with (
            httpx.AsyncClient() as client,
            client.stream("GET", reference_storage_url) as response,
        ):
            response.raise_for_status()
            async for line in response.aiter_lines():
                reference = Reference.model_validate_json(line)
                references.append(reference)
        return references

    async def upload_enhancements(
        self,
        enhancements: list[Enhancement],
        result_storage_url: str,
    ) -> None:
        """
        Upload enhancements to a given URL.

        Args:
            enhancements (list[Enhancement]): A list of Enhancement objects to upload.
            result_storage_url (str): The URL to upload enhancements to.

        """
        file_content = b""
        for enhancement in enhancements:
            file_content += (enhancement.to_jsonl() + "\n").encode("utf-8")

        async with httpx.AsyncClient() as client:
            response = await client.put(
                result_storage_url,
                content=file_content,
                headers={
                    "Content-Type": "application/jsonl",
                    "x-ms-blob-type": "BlockBlob",
                    "Content-Length": str(len(file_content)),
                },
            )
            response.raise_for_status()

    async def process_batch(self, batch: RobotEnhancementBatch) -> list[Enhancement]:
        """
        Process a batch by downloading references and creating enhancements.

        Args:
            batch (RobotEnhancementBatch): The batch of `Reference`s to enhance.

        Returns:
            list[Enhancement]: The list of generated enhancements.

        """
        logger.info("Processing robot enhancement batch {}", batch.id)
        references = await self.download_references(str(batch.reference_storage_url))
        logger.debug(f"References: {references}")
        try:
            generated_enhancements = self.create_abstract_enhancement(
                references=references,
            )
            await self.upload_enhancements(
                enhancements=generated_enhancements,
                result_storage_url=str(batch.result_storage_url),
            )
        except BatchEnhancementGenerationError as full_batch_failure:
            error_message = (
                "Full batch failure during enhancement generation for"
                f" batch {batch.id}:"
                f" {full_batch_failure}"
            )
            logger.error(
                error_message,
                batch.id,
                full_batch_failure,
            )
            raise FullBatchFailureError(error_message) from full_batch_failure
        return generated_enhancements
