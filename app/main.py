"""Main module for the Fetch Abstracts Robot."""

import uuid
from importlib.metadata import version as robot_version
from typing import Final
from uuid import UUID

import destiny_sdk
import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, Response, status

from app.auth import abstract_collector_auth
from app.config import get_settings

settings = get_settings()

TITLE: Final[str] = "Fetch Abstracts Robot (FAR)"
app = FastAPI(title=TITLE)

client = destiny_sdk.client.Client(
    base_url=settings.destiny_repository_url,
    client_id=settings.robot_id,
    secret_key=settings.robot_secret,
)


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
    reference_id: UUID,
) -> destiny_sdk.enhancements.Enhancement:
    """Generate an abstract enhancement."""
    # TO DO:
    # - go through approaches for getting abstract
    # given a DOI
    # - if retrieval was successful, validate & extract
    # the required info and plug into the return statement
    # below, if not, raise an error?
    the_abstract = "This is a placeholder abstract."

    return destiny_sdk.enhancements.Enhancement(
        reference_id=reference_id,
        source=TITLE,
        visibility=destiny_sdk.visibility.Visibility.PUBLIC,
        robot_version=str(robot_version),
        content_version=f"{uuid.uuid4()}",
        content=destiny_sdk.enhancements.AnnotationEnhancement(
            annotations=[
                destiny_sdk.enhancements.AbstractContentEnhancement(
                    process=destiny_sdk.enhancements.AbstractProcessType.OTHER,  # NOTE -- unsure whether this is the right process type for our abstract?
                    abstract=the_abstract,
                )
            ]
        ),
    )


def create_abstract_enhancement(request: destiny_sdk.robots.RobotRequest) -> None:
    """Create a toy enhancement."""
    enhancement = generate_abstract_enhancement(request.reference.id)

    client.send_robot_result(
        destiny_sdk.robots.RobotResult(request_id=request.id, enhancement=enhancement)
    )


def create_batch_abstract_enhancement(
    request: destiny_sdk.robots.BatchRobotRequest,
) -> None:
    """Create a batch of abstract enhancements with efficient memory usage."""
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
def request_toy_enhancement(
    request: destiny_sdk.robots.RobotRequest, background_tasks: BackgroundTasks
) -> Response:
    """Receive a request to create a toy enhancement."""
    background_tasks.add_task(create_abstract_enhancement, request)

    return Response(status_code=status.HTTP_202_ACCEPTED)


@app.post(
    "/abstract/enhancement/batch/",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(abstract_collector_auth)],
)
def request_batch_toy_enhancement(
    request: destiny_sdk.robots.BatchRobotRequest, background_tasks: BackgroundTasks
) -> Response:
    """Receive a request to create a lot of toy enhancements."""
    background_tasks.add_task(create_batch_abstract_enhancement, request)

    return Response(status_code=status.HTTP_202_ACCEPTED)
