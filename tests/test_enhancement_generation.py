import json
import uuid

import pytest
from destiny_sdk.enhancements import (
    AbstractContentEnhancement,
    AbstractProcessType,
    Enhancement,
)
from destiny_sdk.references import Reference
from destiny_sdk.robots import LinkedRobotError
from destiny_sdk.visibility import Visibility
from requests import HTTPError

from app.data_models.generic import AbstractNotFoundError
from app.enhancement_generation import (
    BatchEnhancementGenerationError,
    generate_abstract_enhancement_batch_request,
    generate_abstract_enhancement_single_request,
)


def test_generate_abstract_enhancement_single_request_success(
    mocker, test_settings, scopus_api_config_valid_single
):
    """Test generating a single abstract enhancement request."""
    test_doi = "10.1093/ajae/aaq063"
    test_id = uuid.uuid4()
    test_reference = Reference(
        id=test_id,
        identifiers=[{"identifier": test_doi, "identifier_type": "doi"}],
        enhancements=[],
    )
    mocked_abstract_text = "This is a mocked abstract."
    mocked_enhancement_dict = {
        "doi": test_doi,
        "abstract": mocked_abstract_text,
        "source": "crossref",
    }
    abstract_fetcher = mocker.MagicMock()
    mocker.patch.object(
        abstract_fetcher,
        "get_one_abstract_cycling_apis",
        return_value=mocked_enhancement_dict,
    )

    test_version_number = "9.9.9"
    test_app_title = "test app title"
    mocker.patch(
        "app.enhancement_generation.get_version_number",
        return_value=test_version_number,
    )
    expected_result = Enhancement(
        reference_id=test_reference.id,
        source=test_app_title,
        visibility=Visibility.PUBLIC,
        robot_version=test_version_number,
        content_version=f"{uuid.uuid4()}",
        content=AbstractContentEnhancement(
            process=AbstractProcessType.CLOSED_API,
            abstract=mocked_abstract_text,
        ),
    )

    result = generate_abstract_enhancement_single_request(
        abstract_fetcher=abstract_fetcher,
        reference=test_reference,
        app_title=test_app_title,
    )
    assert isinstance(result, Enhancement)
    assert result == expected_result
    assert mocked_abstract_text in result.content.abstract


def test_generate_abstract_enhancement_single_request_failure_abstract_not_found(
    mocker, caplog, set_test_environment_variables
):
    """Test generating a single abstract enhancement request failure."""
    from app.main import generate_abstract_enhancement_single_request

    test_doi = "10.1093/ajae/aaq063"
    test_id = uuid.uuid4()
    test_reference = Reference(
        id=test_id,
        identifiers=[{"identifier": test_doi, "identifier_type": "doi"}],
        enhancements=[],
    )

    abstract_fetcher = mocker.MagicMock()
    mocker.patch.object(
        abstract_fetcher,
        "get_one_abstract_cycling_apis",
        side_effect=AbstractNotFoundError("A test error"),
    )
    test_app_title = "A test app, doomed to failure."
    with caplog.at_level("ERROR"), pytest.raises(AbstractNotFoundError) as excinfo:
        generate_abstract_enhancement_single_request(
            abstract_fetcher=abstract_fetcher,
            reference=test_reference,
            app_title=test_app_title,
        )
    assert str(excinfo.value) == "A test error"
    assert f"Abstract not found for DOI: {test_doi}" in caplog.text


def test_generate_abstract_enhancement_single_request_failure_http_error(
    mocker, caplog, set_test_environment_variables
):
    """Test generating a single abstract enhancement request failure."""
    from app.main import generate_abstract_enhancement_single_request

    test_doi = "10.1093/ajae/aaq063"
    test_id = uuid.uuid4()
    test_reference = Reference(
        id=test_id,
        identifiers=[{"identifier": test_doi, "identifier_type": "doi"}],
        enhancements=[],
    )
    test_error_text = "A test error"
    abstract_fetcher = mocker.MagicMock()
    mocker.patch.object(
        abstract_fetcher,
        "get_one_abstract_cycling_apis",
        side_effect=HTTPError(test_error_text),
    )
    test_app_title = "A test app, doomed to failure."
    with caplog.at_level("ERROR"), pytest.raises(HTTPError) as excinfo:
        generate_abstract_enhancement_single_request(
            abstract_fetcher=abstract_fetcher,
            reference=test_reference,
            app_title=test_app_title,
        )
    assert str(excinfo.value) == "A test error"
    assert f"HTTP error occurred: {test_error_text}" in caplog.text


def test_generate_abstract_enhancement_batch_request_success(
    mocker, test_settings, scopus_api_config_valid_batch
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

    result = generate_abstract_enhancement_batch_request(
        references=test_two_references,
        enhancements_references_map=test_enhancement_references_map,
        available_api_configs=available_api_configs,
        app_title=test_app_title,
    )

    assert isinstance(result, bytes)
    result_string = result.decode("utf-8")

    assert (
        f"This is a mocked abstract for {test_two_references[0].id}." in result_string
    )
    assert (
        f"This is a mocked abstract for {test_two_references[1].id}." in result_string
    )


def test_generate_abstract_enhancement_batch_request_total_failure_empty_reference_id_in_map(
    mocker, test_settings, scopus_api_config_valid_batch
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
        generate_abstract_enhancement_batch_request(
            references=test_two_references,
            enhancements_references_map=test_enhancement_references_map,
            available_api_configs=available_api_configs,
            app_title=test_app_title,
        )

    assert "Reference ID is missing in the enhancements map." in str(excinfo.value)


def test_generate_abstract_enhancement_batch_request_partial_success_empty_abstracts_found_for_some_references(
    mocker, test_settings, scopus_api_config_valid_batch
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

    result = generate_abstract_enhancement_batch_request(
        references=test_two_references,
        enhancements_references_map=test_enhancement_references_map,
        available_api_configs=available_api_configs,
        app_title=test_app_title,
    )
    byte_encoded_expected_error = expected_error.to_jsonl().encode("utf-8")
    assert (
        byte_encoded_expected_error in result
    ), "Expect a LinkedRobotError for the missing abstract but normal enhancements otherwise."


def test_generate_abstract_enhancement_batch_request_appropriate_visibility(
    mocker, test_settings, scopus_api_config_valid_batch
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

    result = generate_abstract_enhancement_batch_request(
        references=test_two_references,
        enhancements_references_map=test_enhancement_references_map,
        available_api_configs=available_api_configs,
        app_title=test_app_title,
    )

    result_string_list = result.decode("utf-8").splitlines()
    results_split = [json.loads(line) for line in result_string_list]
    assert (
        results_split[0]["visibility"].upper() == "RESTRICTED"
    ), "Expect RESTRICTED visibility for SCOPUS sourced abstract."
    assert (
        results_split[1]["visibility"].upper() == "PUBLIC"
    ), "Expect PUBLIC visibility for crossref sourced abstract."


def test_generate_abstract_enhancement_batch_request_total_failure_no_abstracts_found_for_any_reference(
    mocker, test_settings, scopus_api_config_valid_batch
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
        generate_abstract_enhancement_batch_request(
            references=test_two_references,
            enhancements_references_map=test_enhancement_references_map,
            available_api_configs=available_api_configs,
            app_title=test_app_title,
        )

    assert expected_error_message in str(excinfo.value)
