"""Test the main module."""

import uuid

import destiny_sdk
from fastapi import status
from pytest_httpx import HTTPXMock, IteratorStream
from pytest_mock import MockerFixture


def mock_reference_file_stream(
    httpx_mock: HTTPXMock, reference_ids: list[uuid.UUID], dois: list[str]
):
    """Mock a stream for a file containing references."""
    stream_response = []
    for reference_id, doi in zip(reference_ids, dois, strict=False):
        reference = destiny_sdk.references.Reference(
            id=reference_id,
            identifiers=[destiny_sdk.identifiers.DOIIdentifier(identifier=doi)],
        )
        stream_response.append(bytes(reference.to_jsonl() + "\n", "utf-8"))
    httpx_mock.add_response(stream=IteratorStream(stream_response))


def mock_destiny_repository_response(
    httpx_mock: HTTPXMock, request_id: uuid.UUID, reference_ids: list[uuid.UUID]
):
    """Mock a successful enhancement post to destiny repository."""
    create_enhancement_response = destiny_sdk.robots.EnhancementRequestRead(
        id=request_id,
        reference_ids=reference_ids,
        enhancement_parameters={},
        robot_id=uuid.uuid4(),
        request_status=destiny_sdk.robots.EnhancementRequestStatus.COMPLETED,
    )

    # Mock out our callback
    httpx_mock.add_response(
        method="POST",
        status_code=status.HTTP_200_OK,
        json=create_enhancement_response.model_dump(mode="json"),
    )


def mock_enhancement_put(httpx_mock: HTTPXMock):
    """Mock the putting of references to the results url."""
    httpx_mock.add_response(method="PUT", status_code=status.HTTP_200_OK)


def test_root(test_client) -> None:
    """Test the root endpoint."""
    response = test_client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"message": "I am the Fetch Abstracts Robot (FAR)."}


def test_health(test_client) -> None:
    """Test the health endpoint."""
    response = test_client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "healthy"}


def test_create_abstract_enhancement_happy_path(
    httpx_mock: HTTPXMock, mocker: MockerFixture, test_client
) -> None:
    """Test that we can create an enhancement."""
    request_id = uuid.uuid4()
    reference_ids = [uuid.uuid4() for _ in range(3)]
    dois = [f"10.1000/xyz12{i}" for i in range(3)]
    mock_reference_file_stream(httpx_mock, reference_ids, dois)
    mock_destiny_repository_response(httpx_mock, request_id, reference_ids)
    mock_enhancement_put(httpx_mock)

    request_body = destiny_sdk.robots.RobotRequest(
        id=uuid.uuid4(),
        reference_storage_url="http://example.com/references",
        result_storage_url="http://example.com/results",
    ).model_dump(mode="json")

    expected_external_api_response = {
        "message": {"abstract": "This is a test abstract."}
    }
    mocker.patch(
        "app.fetch_abstract.requests.get",
        return_value=mocker.Mock(
            status_code=200, json=lambda: expected_external_api_response
        ),
    )
    response = test_client.post("/abstract/enhancement/batch/", json=request_body)

    assert (
        response.status_code == status.HTTP_202_ACCEPTED
    ), "Expect that request is accepted."

    callback_requests = httpx_mock.get_requests()
    assert (
        len(callback_requests) == 3
    ), "Expect that the background task has been called."

    put_request = callback_requests[1]
    generated_enhancements = put_request.content.decode("utf-8").strip().split("\n")
    assert (
        len(generated_enhancements) == 3
    ), "Expect that we have 3 enhancements generated."

    for enhancement in generated_enhancements:
        destiny_sdk.enhancements.Enhancement.from_jsonl(enhancement)
