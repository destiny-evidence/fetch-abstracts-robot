"""Main module for the Fetch Abstracts Robot."""

from typing import Final

import httpx
from destiny_sdk.client import Client as DestinyClient
from destiny_sdk.references import Reference
from destiny_sdk.robots import (
    RobotError,
    RobotRequest,
    RobotResult,
)
from fastapi import BackgroundTasks, Depends, FastAPI, Response, status
from loguru import logger

from app.auth import auth_strategy_robot
from app.config import get_settings
from app.data_models.crossref import get_crossref_batch_api_config
from app.data_models.scopus import get_scopus_batch_api_config
from app.enhancement_generation import (
    BatchEnhancementGenerationError,
    generate_abstract_enhancement_batch_request,
)
from app.fetch_abstract import AbstractFetcher, prepare_api_config
from app.utils import get_doi_from_reference

settings = get_settings()
abstract_collector_auth = auth_strategy_robot(settings=settings)

TITLE: Final[str] = settings.robot_title
app = FastAPI(title=TITLE)

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

# our abstract fetcher util we will use in abstract/enhancement functions in this module
abstract_fetcher = AbstractFetcher(global_api_config)


@app.get("/")
async def root() -> dict[str, str]:
    """
    Root endpoint for the API.

    Returns:
        dict[str, str]: A simple message.

    """
    return {"message": f"I am the {TITLE}."}


@app.get("/health")
async def health_check() -> dict[str, str]:
    """
    Health check endpoint for the API.

    Returns:
        dict[str, str]: A simple health status message.

    """
    return {"status": "healthy"}


def create_abstract_enhancement(
    request: RobotRequest,
) -> None:
    """
    Create abstract enhancements with efficient memory usage.

    This operates on a batch of references as a default,
    but that could be a batch of one.

    This leverages the `get_many_abstracts_cycling_apis` method,
    rather than strictly looping over individual requests (although
    this may be done in the background, depending on API config).
    """
    with (
        httpx.Client() as httpx_client,
        httpx_client.stream("GET", str(request.reference_storage_url)) as response,
    ):
        response.raise_for_status()

        references = [
            Reference.model_validate_json(entry) for entry in response.iter_lines()
        ]
        dois = [get_doi_from_reference(ref) for ref in references]

        abstracts_dois_dict = abstract_fetcher.get_many_abstracts_cycling_apis(dois)

        enhancement_reference_map = [
            {
                "id": ref.id,
                "doi": abstract_doi.get("doi"),
                "abstract": abstract_doi.get("abstract"),
            }
            for ref in references
            for abstract_doi in abstracts_dois_dict
            if get_doi_from_reference(ref) == abstract_doi.get("doi")
        ]

        try:
            file_content = generate_abstract_enhancement_batch_request(
                references=references,
                enhancements_references_map=enhancement_reference_map,
                available_api_configs=AVAILABLE_API_CONFIGS,
                app_title=TITLE,
            )
        except BatchEnhancementGenerationError as batch_error:
            error_message = (
                f"Failed to generate enhancement request: {batch_error}."
                " Failing entire request."
            )
            logger.error(error_message)
            client.send_robot_result(
                RobotResult(
                    request_id=request.id, error=RobotError(message=str(batch_error))
                )
            )
            return
    logger.info("Generated enhancements. Uploading to storage.")
    with httpx.Client() as httpx_client:
        response = httpx_client.put(
            str(request.result_storage_url),
            content=file_content,
            headers={
                "Content-Type": "application/jsonl",
                "x-ms-blob-type": "BlockBlob",
                "Content-Length": str(len(file_content)),
            },
        )
        response.raise_for_status()

    logger.info(f"Enhancements uploaded to {request.result_storage_url}.")
    client.send_robot_result(
        RobotResult(request_id=request.id, storage_url=request.result_storage_url)
    )
    logger.success(f"Enhancements successfully processed for {request.id}.")


@app.post(
    "/abstract/enhancement/batch/",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(abstract_collector_auth)],
)
def request_abstract_enhancements(
    request: RobotRequest, background_tasks: BackgroundTasks
) -> Response:
    """Receive a request to create one or many abstract enhancements."""
    background_tasks.add_task(create_abstract_enhancement, request)

    return Response(status_code=status.HTTP_202_ACCEPTED)
