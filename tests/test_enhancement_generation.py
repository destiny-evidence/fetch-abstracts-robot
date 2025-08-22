import uuid

import pytest
from destiny_sdk.enhancements import (
    AbstractContentEnhancement,
    AbstractProcessType,
    Enhancement,
)
from destiny_sdk.references import Reference
from destiny_sdk.visibility import Visibility

from app.data_models.generic import AbstractNotFoundError
from app.enhancement_generation import generate_abstract_enhancement_single_request


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
