"""Main module for the Fetch Abstracts Robot."""

import uuid
from typing import Final

import destiny_sdk
import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, Response, status

from app.auth import auth_strategy_robot
from app.config import get_settings
from app.data_models.crossref import crossref_api_config
from app.data_models.scopus import scopus_api_config, scopus_batch_api_config
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
    scopus_api_config,
    scopus_batch_api_config,
    crossref_api_config,
]
global_api_config = prepare_api_config(api_configs=AVAILABLE_API_CONFIGS, settings=settings)

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
    abstract_object = abstract_fetcher.get_one_abstract_cycling_apis(doi=doi)
    abstract = abstract_object["abstract"]  # @ NOTE - @harryjmoss maybe we implement its own pydantic model for this?

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
    Create an abstract enhancement.

    this wraps around `generate_abstract_enhancement` and queues it.
    """
    enhancement = generate_abstract_enhancement(request.reference)

    client.send_robot_result(destiny_sdk.robots.RobotResult(request_id=request.id, enhancement=enhancement))


def create_batch_abstract_enhancement(
    request: destiny_sdk.robots.BatchRobotRequest,
) -> None:
    """
    Create a batch of abstract enhancements with efficient memory usage.

    This leverages the `get_many_abstracts_cycling_apis` method,
    rather than strictly looping over individual requests (although
    this may be done in the background, depending on API config).
    """
    version_number = get_version_number_from_pyproject()
    file_content = b""
    with (
        httpx.Client() as httpx_client,
        httpx_client.stream("GET", str(request.reference_storage_url)) as response,
    ):
        response.raise_for_status()

        references_in = [destiny_sdk.references.Reference.model_validate_json(entry) for entry in response.iter_lines()]
        dois = [get_doi_from_reference(ref) for ref in references_in]

        abstracts = abstract_fetcher.get_many_abstracts_cycling_apis(dois)

        references_out = [
            ref for ref in references_in if get_doi_from_reference(ref) in [abstract["doi"] for abstract in abstracts]
        ]

        for ref, ab in zip(references_out, abstracts, strict=True):
            file_content += (
                destiny_sdk.enhancements.Enhancement(
                    reference_id=ref.id,
                    source=TITLE,
                    visibility=destiny_sdk.visibility.Visibility.PUBLIC,
                    robot_version=version_number,
                    content_version=f"{uuid.uuid4()}",
                    enhancement_type=destiny_sdk.enhancements.EnhancementType.ABSTRACT,
                    content=destiny_sdk.enhancements.AbstractContentEnhancement(
                        process=destiny_sdk.enhancements.AbstractProcessType.CLOSED_API,
                        abstract=ab["abstract"],
                    ),
                ).to_jsonl()
                + "\n"
            ).encode("utf-8")

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
        destiny_sdk.robots.BatchRobotResult(request_id=request.id, storage_url=request.result_storage_url)
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
    """Receive a request to create many abstract enhancements."""
    background_tasks.add_task(create_batch_abstract_enhancement, request)

    return Response(status_code=status.HTTP_202_ACCEPTED)
