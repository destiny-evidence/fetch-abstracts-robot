import uuid

import pytest
from destiny_sdk.enhancements import Enhancement
from destiny_sdk.references import Reference
from destiny_sdk.robots import LinkedRobotError, RobotRequest
from fastapi import status
from pytest_httpx import HTTPXMock
from pytest_mock import MockerFixture

from app.config import Settings
from app.enhancement_processor import (
    AbstractEnhancementProcessor,
    BatchEnhancementGenerationError,
)


@pytest.mark.xfail(
    reason="Test needs to be updated to reflect new robot polling workflow."
)
def test_create_abstract_enhancement(
    httpx_mock: HTTPXMock,
    mocker: MockerFixture,
    test_client,
    mock_reference_file_stream,
    mock_destiny_repository_response,
    mock_enhancement_put,
) -> None:
    """Test that we can create an enhancement."""
    request_id = uuid.uuid4()
    reference_ids = [uuid.uuid4() for _ in range(3)]
    dois = [f"10.1000/xyz12{i}" for i in range(3)]
    mock_reference_file_stream(httpx_mock, reference_ids, dois)
    mock_destiny_repository_response(httpx_mock, request_id, reference_ids)
    mock_enhancement_put(httpx_mock)

    request_body = RobotRequest(
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
        Enhancement.from_jsonl(enhancement)


def test_generate_abstract_enhancement_batch_request_success(
    mocker,
    test_settings: Settings,
    test_abstract_enhancement_processor: AbstractEnhancementProcessor,
    scopus_api_config_valid_batch,
):
    test_two_references = [
        Reference(
            id=uuid.uuid4(),
            identifiers=[
                {"identifier": "10.1093/ajae/aaq063", "identifier_type": "doi"}
            ],
            enhancements=[],
        ),
        Reference(
            id=uuid.uuid4(),
            identifiers=[
                {"identifier": "10.1093/ajae/aaq064", "identifier_type": "doi"}
            ],
            enhancements=[],
        ),
    ]

    test_enhancement_references_map = [
        {
            "id": ref.id,
            "abstract": f"This is a mocked abstract for {ref.id}.",
        }
        for ref in test_two_references
    ]
    available_api_configs = [scopus_api_config_valid_batch]
    test_app_title = "A test app for batch requests."

    result = (
        test_abstract_enhancement_processor.generate_abstract_enhancement_batch_request(
            references=test_two_references,
            enhancements_references_map=test_enhancement_references_map,
            available_api_configs=available_api_configs,
            app_title=test_app_title,
        )
    )

    assert len(result) == len(test_two_references)
    assert all(isinstance(result_item, Enhancement) for result_item in result)

    assert all(
        (
            f"This is a mocked abstract for {test_two_references[i].id}."
            in result_item.content.abstract
            for i, result_item in enumerate(result)
        )
    )


def test_generate_abstract_enhancement_batch_request_total_failure_empty_reference_id_in_map(
    mocker,
    test_settings,
    test_abstract_enhancement_processor,
    scopus_api_config_valid_batch,
):
    test_two_references = [
        Reference(
            id=uuid.uuid4(),
            identifiers=[
                {"identifier": "10.1093/ajae/aaq063", "identifier_type": "doi"}
            ],
            enhancements=[],
        ),
        Reference(
            id=uuid.uuid4(),
            identifiers=[
                {"identifier": "10.1093/ajae/aaq064", "identifier_type": "doi"}
            ],
            enhancements=[],
        ),
    ]

    test_enhancement_references_map = [
        {
            "id": None,
            "abstract": f"This is a mocked abstract for {ref.id}.",
        }
        for ref in test_two_references
    ]
    available_api_configs = [scopus_api_config_valid_batch]
    test_app_title = "A test app for batch requests."

    with pytest.raises(BatchEnhancementGenerationError) as excinfo:
        test_abstract_enhancement_processor.generate_abstract_enhancement_batch_request(
            references=test_two_references,
            enhancements_references_map=test_enhancement_references_map,
            available_api_configs=available_api_configs,
            app_title=test_app_title,
        )

    assert "Reference ID is missing in the enhancements map." in str(excinfo.value)


def test_generate_abstract_enhancement_batch_request_partial_success_empty_abstracts_found_for_some_references(
    mocker,
    test_settings,
    test_abstract_enhancement_processor,
    scopus_api_config_valid_batch,
):
    test_two_references = [
        Reference(
            id=uuid.uuid4(),
            identifiers=[
                {"identifier": "10.1093/ajae/aaq063", "identifier_type": "doi"}
            ],
            enhancements=[],
        ),
        Reference(
            id=uuid.uuid4(),
            identifiers=[
                {"identifier": "10.1093/ajae/aaq064", "identifier_type": "doi"}
            ],
            enhancements=[],
        ),
    ]

    test_enhancement_references_map = [
        {
            "id": test_two_references[0].id,
            "abstract": f"This is a mocked abstract for {test_two_references[0].id}.",
        },
        {
            "id": test_two_references[1].id,
            "abstract": None,
        },
    ]
    expected_error = LinkedRobotError(
        message="No abstract found in {'SCOPUS'}",
        reference_id=test_two_references[1].id,
    )
    available_api_configs = [scopus_api_config_valid_batch]
    test_app_title = "A test app for batch requests."

    result = (
        test_abstract_enhancement_processor.generate_abstract_enhancement_batch_request(
            references=test_two_references,
            enhancements_references_map=test_enhancement_references_map,
            available_api_configs=available_api_configs,
            app_title=test_app_title,
        )
    )
    assert len(result) == len(test_two_references)
    assert any(isinstance(result_item, Enhancement) for result_item in result)
    assert (
        expected_error in result
    ), "Expect a LinkedRobotError for the missing abstract but normal enhancements otherwise."


def test_generate_abstract_enhancement_batch_request_appropriate_visibility(
    mocker,
    test_settings,
    test_abstract_enhancement_processor,
    scopus_api_config_valid_batch,
):
    test_two_references = [
        Reference(
            id=uuid.uuid4(),
            identifiers=[
                {"identifier": "10.1093/ajae/aaq063", "identifier_type": "doi"}
            ],
            enhancements=[],
        ),
        Reference(
            id=uuid.uuid4(),
            identifiers=[
                {"identifier": "10.1093/ajae/aaq064", "identifier_type": "doi"}
            ],
            enhancements=[],
        ),
    ]

    test_enhancement_references_map = [
        {
            "id": test_two_references[0].id,
            "abstract": f"This is a mocked abstract for {test_two_references[0].id}.",
            "source": "SCOPUS",
        },
        {
            "id": test_two_references[1].id,
            "abstract": f"This is a mocked abstract for {test_two_references[1].id}.",
            "source": "crossref",
        },
    ]
    available_api_configs = [scopus_api_config_valid_batch]
    test_app_title = "A test app for batch requests."

    result = (
        test_abstract_enhancement_processor.generate_abstract_enhancement_batch_request(
            references=test_two_references,
            enhancements_references_map=test_enhancement_references_map,
            available_api_configs=available_api_configs,
            app_title=test_app_title,
        )
    )

    assert (
        result[0].visibility.upper() == "RESTRICTED"
    ), "Expect RESTRICTED visibility for SCOPUS sourced abstract."
    assert (
        result[1].visibility.upper() == "PUBLIC"
    ), "Expect PUBLIC visibility for crossref sourced abstract."


def test_generate_abstract_enhancement_batch_request_total_failure_no_abstracts_found_for_any_reference(
    mocker,
    test_settings,
    test_abstract_enhancement_processor,
    scopus_api_config_valid_batch,
):
    test_two_references = [
        Reference(
            id=uuid.uuid4(),
            identifiers=[
                {"identifier": "10.1093/ajae/aaq063", "identifier_type": "doi"}
            ],
            enhancements=[],
        ),
        Reference(
            id=uuid.uuid4(),
            identifiers=[
                {"identifier": "10.1093/ajae/aaq064", "identifier_type": "doi"}
            ],
            enhancements=[],
        ),
    ]

    test_enhancement_references_map = [
        {
            "id": ref.id,
            "abstract": None,
            "source": None,
        }
        for ref in test_two_references
    ]
    available_api_configs = [scopus_api_config_valid_batch]
    test_app_title = "A test app for batch requests."

    reference_ids_attempted = ", ".join([str(ref.id) for ref in test_two_references])
    expected_error_message = f"No successful enhancements generated for reference IDs {reference_ids_attempted}"
    with pytest.raises(BatchEnhancementGenerationError) as excinfo:
        test_abstract_enhancement_processor.generate_abstract_enhancement_batch_request(
            references=test_two_references,
            enhancements_references_map=test_enhancement_references_map,
            available_api_configs=available_api_configs,
            app_title=test_app_title,
        )

    assert expected_error_message in str(excinfo.value)
