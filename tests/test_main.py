"""Test the main module."""

import uuid
from unittest.mock import patch

import destiny_sdk
import httpx
import pytest
from pytest_httpx import HTTPXMock, IteratorStream

from far.enhancements.processor import AbstractEnhancementProcessor
from far.main import process_robot_enhancement_batch


def test_generate_abstract_enhancement(
    mocker,
    test_abstract_enhancement_processor: AbstractEnhancementProcessor,
    scopus_api_config_valid_batch,
    crossref_api_config_valid_batch,
    pubmed_api_config_valid_batch,
) -> None:
    """Test that abstract enhancements are generated with valid abstracts."""
    reference_ids = [uuid.uuid4() for _ in range(3)]
    test_abstracts = [
        {"doi": f"10.1000/{i}", "abstract": f"This is abstract {i}."} for i in range(3)
    ]
    available_api_configs = [
        scopus_api_config_valid_batch,
        crossref_api_config_valid_batch,
        pubmed_api_config_valid_batch,
    ]

    output_enhancements = [
        destiny_sdk.enhancements.Enhancement(
            reference_id=ref_id,
            source="Test Robot",
            visibility=destiny_sdk.visibility.Visibility.HIDDEN,
            robot_version="9.9.9",
            content_version=f"{uuid.uuid4()}",
            content=destiny_sdk.enhancements.AbstractContentEnhancement(
                process=destiny_sdk.enhancements.AbstractProcessType.CLOSED_API,
                abstract=abstract_doi.get("abstract"),
            ),
        )
        for ref_id, abstract_doi in zip(reference_ids, test_abstracts, strict=False)
    ]
    mocker.patch.object(
        test_abstract_enhancement_processor,
        "generate_abstract_enhancement_batch_request",
        return_value=output_enhancements,
    )

    enhancement_reference_map = [
        {
            "id": ref,
            "doi": abstract_doi.get("doi"),
            "abstract": abstract_doi.get("abstract"),
        }
        for ref in reference_ids
        for abstract_doi in test_abstracts
    ]

    enhancements = (
        test_abstract_enhancement_processor.generate_abstract_enhancement_batch_request(
            reference_ids,
            enhancement_reference_map,
            available_api_configs,
            app_title="Test Robot",
        )
    )

    assert len(enhancements) == 3, "Expect that we have 3 enhancements generated."
    expected_abstracts = [
        abstract_doi.get("abstract") for abstract_doi in test_abstracts
    ]
    for enhancement in enhancements:
        assert isinstance(enhancement, destiny_sdk.enhancements.Enhancement)
        assert enhancement.content.abstract in expected_abstracts
        assert enhancement.reference_id in reference_ids


@pytest.mark.asyncio
async def test_process_robot_enhancement_batch_happy_path(
    mocker,
    httpx_mock: HTTPXMock,
    test_abstract_enhancement_processor: AbstractEnhancementProcessor,
) -> None:
    """Test successful processing of a robot enhancement batch."""
    batch_id = uuid.uuid4()
    reference_ids = [uuid.uuid4() for _ in range(3)]
    dois = [f"10.1000/{i}" for i in range(3)]
    abstracts = [f"This is abstract {i}." for i in range(3)]

    # Mock the batch data
    batch = destiny_sdk.robots.RobotEnhancementBatch(
        id=batch_id,
        reference_storage_url="https://get-references-here.com",
        result_storage_url="https://put-results-here.com",
    )

    # Mock reference file download
    mock_reference_file_stream(httpx_mock, reference_ids, dois)

    # Mock result upload
    httpx_mock.add_response(method="PUT", status_code=200)

    test_fetch_many_abstracts_return_value = [
        {"doi": doi, "abstract": abstract}
        for doi, abstract in zip(dois, abstracts, strict=False)
    ]
    mocker.patch(
        "far.fetch_abstract.AbstractFetcher.get_many_abstracts_cycling_apis",
        return_value=test_fetch_many_abstracts_return_value,
    )

    # Mock SDK result submission
    with (
        patch("far.main.DestinyClient") as mock_client,
    ):
        await process_robot_enhancement_batch(
            mock_client, test_abstract_enhancement_processor, batch
        )

        mock_client.send_robot_enhancement_batch_result.assert_called_once()
        call_args = mock_client.send_robot_enhancement_batch_result.call_args[0][0]
        assert call_args.request_id == batch_id, "Request ID should match."
        assert call_args.error is None, "There should be no error."


@pytest.mark.asyncio
async def test_process_robot_enhancement_batch_with_download_error(
    httpx_mock: HTTPXMock,
    test_abstract_enhancement_processor: AbstractEnhancementProcessor,
) -> None:
    """Test handling of download errors during batch processing."""
    batch_id = uuid.uuid4()

    batch = destiny_sdk.robots.RobotEnhancementBatch(
        id=batch_id,
        reference_storage_url="https://get-references-here.com",
        result_storage_url="https://put-results-here.com",
    )

    # Mock download failure
    httpx_mock.add_response(method="GET", status_code=404)

    with patch("far.main.DestinyClient") as mock_client:
        # Process should raise an exception due to HTTP error
        with pytest.raises(httpx.HTTPStatusError, match="404"):
            await process_robot_enhancement_batch(
                mock_client, test_abstract_enhancement_processor, batch
            )

        # Verify error result was sent
        mock_client.send_robot_enhancement_batch_result.assert_called_once()
        call_args = mock_client.send_robot_enhancement_batch_result.call_args[0][0]
        assert call_args.request_id == batch_id
        assert call_args.error is not None


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
