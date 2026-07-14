import uuid

import pytest
from destiny_sdk.enhancements import (
    AbstractContentEnhancement,
    AbstractProcessType,
    Enhancement,
)
from destiny_sdk.references import Reference
from destiny_sdk.robots import LinkedRobotError, RobotEnhancementBatch
from pytest_httpx import HTTPXMock
from pytest_mock import MockerFixture

from far.config import Settings
from far.enhancement_processor import (
    AbstractEnhancementProcessor,
    BatchEnhancementGenerationError,
    FullBatchFailureError,
)


def test_create_abstract_enhancement_success(
    mocker: MockerFixture,
    test_abstract_enhancement_processor: AbstractEnhancementProcessor,
    test_references: list[Reference],
) -> None:
    """Test that we can create an enhancement."""
    expected_generate_abstracts_response = [
        Enhancement(
            id=uuid.uuid4(),
            reference_id=test_references[0].id,
            content=AbstractContentEnhancement(
                abstract="This is a test abstract.",
                process=AbstractProcessType.CLOSED_API,
            ),
            source="crossref",
            visibility="public",
            robot_version="9.9.9",
            content_version=str(uuid.uuid4()),
        ),
        Enhancement(
            id=uuid.uuid4(),
            reference_id=test_references[1].id,
            content=AbstractContentEnhancement(
                abstract="This is a test abstract.",
                process=AbstractProcessType.CLOSED_API,
            ),
            source="scopus",
            visibility="restricted",
            robot_version="9.9.9",
            content_version=str(uuid.uuid4()),
        ),
    ]
    test_abstracts_dois_dict = [
        {
            "doi": test_references[0].identifiers[0].identifier,
            "abstract": "This is test abstract 1.",
        },
        {
            "doi": test_references[1].identifiers[0].identifier,
            "abstract": "This is test abstract 2.",
        },
    ]
    cycling_apis_mock = mocker.patch(
        "far.fetch_abstract.AbstractFetcher.get_many_abstracts_cycling_apis",
        return_value=test_abstracts_dois_dict,
    )

    enhancement_generation_mock = mocker.patch(
        "far.enhancement_processor.AbstractEnhancementProcessor.generate_abstract_enhancement_batch_request",
        return_value=expected_generate_abstracts_response,
    )

    result = test_abstract_enhancement_processor.create_abstract_enhancement(
        test_references
    )

    assert isinstance(result, list)
    assert len(result) == len(test_references)
    assert all(isinstance(item, Enhancement) for item in result)

    (
        cycling_apis_mock.assert_called_once(),
        "Expected cycling_apis_mock to be called once per batch of references.",
    )
    (
        enhancement_generation_mock.assert_called_once(),
        "Expected enhancement_generation_mock to be called once per batch of references.",
    )


def test_create_abstract_enhancement_batch_enhancement_generation_failure(
    httpx_mock: HTTPXMock,
    mocker: MockerFixture,
    test_abstract_enhancement_processor: AbstractEnhancementProcessor,
    test_references: list[Reference],
) -> None:
    """Test that we can create an enhancement."""
    test_abstracts_dois_dict = [
        {
            "doi": test_references[0].identifiers[0].identifier,
            "abstract": "This is test abstract 1.",
        },
        {
            "doi": test_references[1].identifiers[0].identifier,
            "abstract": "This is test abstract 2.",
        },
    ]
    cycle_apis_mock = mocker.patch(
        "far.fetch_abstract.AbstractFetcher.get_many_abstracts_cycling_apis",
        return_value=test_abstracts_dois_dict,
    )

    enhancement_generation_mock = mocker.patch(
        "far.enhancement_processor.AbstractEnhancementProcessor.generate_abstract_enhancement_batch_request",
        side_effect=BatchEnhancementGenerationError("Test batch generation error."),
    )

    with pytest.raises(BatchEnhancementGenerationError) as error_info:
        test_abstract_enhancement_processor.create_abstract_enhancement(test_references)
    assert "Test batch generation error." in str(error_info.value)

    cycle_apis_mock.assert_called_once()
    enhancement_generation_mock.assert_called_once()


@pytest.mark.asyncio
async def test_process_batch_success(
    mocker: MockerFixture,
    test_abstract_enhancement_processor: AbstractEnhancementProcessor,
    test_references: list[Reference],
):
    expected_generate_abstracts_response = [
        Enhancement(
            id=uuid.uuid4(),
            reference_id=test_references[0].id,
            content=AbstractContentEnhancement(
                abstract="This is a test abstract.",
                process=AbstractProcessType.CLOSED_API,
            ),
            source="crossref",
            visibility="public",
            robot_version="9.9.9",
            content_version=str(uuid.uuid4()),
        ),
        Enhancement(
            id=uuid.uuid4(),
            reference_id=test_references[1].id,
            content=AbstractContentEnhancement(
                abstract="This is a test abstract.",
                process=AbstractProcessType.CLOSED_API,
            ),
            source="scopus",
            visibility="restricted",
            robot_version="9.9.9",
            content_version=str(uuid.uuid4()),
        ),
    ]

    test_robot_request = RobotEnhancementBatch(
        id=uuid.uuid4(),
        reference_storage_url="http://example.com/references",
        result_storage_url="http://example.com/results",
    )

    download_references_mock = mocker.patch(
        "far.enhancement_processor.AbstractEnhancementProcessor.download_references",
        return_value=test_references,
    )

    create_abstract_enhancement_mock = mocker.patch(
        "far.enhancement_processor.AbstractEnhancementProcessor.create_abstract_enhancement",
        return_value=expected_generate_abstracts_response,
    )

    upload_enhancements_mock = mocker.patch(
        "far.enhancement_processor.AbstractEnhancementProcessor.upload_enhancements",
        return_value=None,
    )

    result = await test_abstract_enhancement_processor.process_batch(test_robot_request)

    assert isinstance(result, list)
    assert len(result) == len(test_references)
    assert all(isinstance(item, Enhancement) for item in result)

    download_references_mock.assert_called_once()
    create_abstract_enhancement_mock.assert_called_once()
    upload_enhancements_mock.assert_called_once()


@pytest.mark.asyncio
async def test_process_batch_full_batch_failure(
    mocker: MockerFixture,
    test_abstract_enhancement_processor: AbstractEnhancementProcessor,
    test_references: list[Reference],
):
    test_robot_request = RobotEnhancementBatch(
        id=uuid.uuid4(),
        reference_storage_url="http://example.com/references",
        result_storage_url="http://example.com/results",
    )

    download_references_mock = mocker.patch(
        "far.enhancement_processor.AbstractEnhancementProcessor.download_references",
        return_value=test_references,
    )

    create_abstract_enhancement_mock = mocker.patch(
        "far.enhancement_processor.AbstractEnhancementProcessor.create_abstract_enhancement",
        side_effect=BatchEnhancementGenerationError("Test batch generation error."),
    )

    upload_enhancements_mock = mocker.patch(
        "far.enhancement_processor.AbstractEnhancementProcessor.upload_enhancements",
        return_value=None,
    )

    with pytest.raises(FullBatchFailureError) as error_info:
        await test_abstract_enhancement_processor.process_batch(test_robot_request)

    assert "Test batch generation error." in str(error_info.value)

    (
        download_references_mock.assert_called_once(),
        "Expect that the references are downloaded via a single call.",
    )
    (
        create_abstract_enhancement_mock.assert_called_once(),
        "Expect that the abstract creation is attempted once for the batch.",
    )
    (
        upload_enhancements_mock.assert_not_called(),
        "Expect that no upload is attempted in this method if the batch generation fails.",
    )


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
    assert expected_error in result, (
        "Expect a LinkedRobotError for the missing abstract but normal enhancements otherwise."
    )


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

    assert result[0].visibility.upper() == "RESTRICTED", (
        "Expect RESTRICTED visibility for SCOPUS sourced abstract."
    )
    assert result[1].visibility.upper() == "PUBLIC", (
        "Expect PUBLIC visibility for crossref sourced abstract."
    )


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
