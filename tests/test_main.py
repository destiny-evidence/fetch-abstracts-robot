"""Test the main module."""

import uuid

import destiny_sdk
from fastapi import status
from fastapi.testclient import TestClient
from pytest_httpx import HTTPXMock


def test_root(test_client: TestClient) -> None:
    """Test the root endpoint."""
    response = test_client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"message": "I am the Fetch Abstracts Robot (FAR)."}


def test_health(test_client: TestClient) -> None:
    """Test the health endpoint."""
    response = test_client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "healthy"}


def test_create_toy_enhancement_happy_path(
    test_client: TestClient, httpx_mock: HTTPXMock
) -> None:
    """Test that we can create an enhancement."""
    request_id = uuid.uuid4()
    reference_id = uuid.uuid4()

    create_enhancement_response = destiny_sdk.robots.EnhancementRequestRead(
        reference_id=reference_id,
        id=request_id,
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

    request_body = {
        "id": f"{request_id}",
        "reference": {"id": f"{reference_id}", "identifiers": [], "enhancements": []},
        "extra_fields": {},
    }

    response = test_client.post("/toy/enhancement/single/", json=request_body)

    assert response.status_code == status.HTTP_202_ACCEPTED

    # Assert the background task has been called.
    callback_request = httpx_mock.get_requests()
    assert len(callback_request) == 1
