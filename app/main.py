"""Main module for the Fetch Abstracts Robot."""

import uuid
from typing import Final

import destiny_sdk
import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, Response, status

from app.auth import auth_strategy_robot
from app.config import get_settings
from app.data_models.scopus import scopus_api_config
from app.fetch_abstract import AbstractFetcher, prepare_api_config
from app.utils import get_doi_from_reference, get_version_number_from_pyproject

settings = get_settings()
abstract_collector_auth = auth_strategy_robot(settings=settings)

TITLE: Final[str] = "Fetch Abstracts Robot (FAR)"
app = FastAPI(title=TITLE)

client = destiny_sdk.client.Client(
    base_url=settings.destiny_repository_url,
    client_id=settings.robot_id,
    secret_key=settings.robot_secret,
)

# configurations for all APIs we can hit to get abstracts
AVAILABLE_API_CONFIGS = [
    scopus_api_config  # add more here as more apis get defined/implemented
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
    return {"message": "I am the Fetch Abstracts Robot (FAR)."}


@app.get("/health")
async def health_check() -> dict[str, str]:
    """
    Health check endpoint for the API.

    Returns:
        dict[str, str]: A simple health status message.

    """
    return {"status": "healthy"}


def generate_abstract_enhancement(
    reference: destiny_sdk.references.Reference,
) -> destiny_sdk.enhancements.Enhancement:
    """Generate an abstract enhancement."""
    doi = get_doi_from_reference(reference=reference)
    abstract = abstract_fetcher.get_abstract_cycling_apis(doi=doi)

    return destiny_sdk.enhancements.Enhancement(
        reference_id=reference.id,
        source=TITLE,
        visibility=destiny_sdk.visibility.Visibility.PUBLIC,
        robot_version=get_version_number_from_pyproject(),
        content_version=f"{uuid.uuid4()}",
        enhancement_type=destiny_sdk.enhancements.EnhancementType.ABSTRACT,
        content=destiny_sdk.enhancements.AbstractContentEnhancement(
            process=destiny_sdk.enhancements.AbstractProcessType.CLOSED_API,
            abstract=abstract,
        ),
    )


def create_abstract_enhancement(request: destiny_sdk.robots.RobotRequest) -> None:
    """
    create an abstract enhancement.

    this wraps around `generate_abstract_enhancement` and queues it.
    """
    enhancement = generate_abstract_enhancement(request.reference)

    client.send_robot_result(
        destiny_sdk.robots.RobotResult(request_id=request.id, enhancement=enhancement)
    )


def create_batch_abstract_enhancement(
    request: destiny_sdk.robots.BatchRobotRequest,
) -> None:
    """
    Create a batch of abstract enhancements with efficient memory usage.

    NOTE -- not yet implemented!
    """
    file_content = b""
    with (
        httpx.Client() as httpx_client,
        httpx_client.stream("GET", str(request.reference_storage_url)) as response,
    ):
        response.raise_for_status()
        for entry in response.iter_lines():
            reference = destiny_sdk.references.Reference.model_validate_json(entry)
            enhancement = generate_abstract_enhancement(reference.id)
            file_content += (enhancement.to_jsonl() + "\n").encode("utf-8")

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

    client.send_batch_robot_result(
        destiny_sdk.robots.BatchRobotResult(
            request_id=request.id, storage_url=request.result_storage_url
        )
    )


@app.post(
    "/abstract/enhancement/single/",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(abstract_collector_auth)],
)
def request_abstract_enhancement(
    request: destiny_sdk.robots.RobotRequest, background_tasks: BackgroundTasks
) -> Response:
    """Receive a request to create an abstract enhancement."""
    background_tasks.add_task(create_abstract_enhancement, request)

    return Response(status_code=status.HTTP_202_ACCEPTED)


@app.post(
    "/abstract/enhancement/batch/",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(abstract_collector_auth)],
)
def request_batch_abstract_enhancement(
    request: destiny_sdk.robots.BatchRobotRequest, background_tasks: BackgroundTasks
) -> Response:
    """
    Receive a request to create a lot of abstract enhancements.

    NOTE - not yet implemented.
    """
    background_tasks.add_task(create_batch_abstract_enhancement, request)

    return Response(status_code=status.HTTP_202_ACCEPTED)
