"""tests for functions in src/app/utils.py."""

from unittest.mock import patch
from uuid import uuid4

import pytest
from destiny_sdk.references import Reference

from app.utils import (
    MissingDOIError,
    get_doi_from_reference,
    get_version_number_from_pyproject,
    validate_doi,
)


class DummyIdentifier:
    """A dummy identifier class to simulate an Identifier object with a DOI."""

    def __init__(self, identifier: str, identifier_type: str = "doi") -> None:
        """
        Initialize the DummyIdentifier with an identifier and type.

        Args:
            identifier (str): The identifier string, typically a DOI.
            identifier_type (str, optional): The type of identifier, default is "doi".

        """
        self.identifier = identifier
        self.identifier_type = identifier_type


class DummyReference:
    """A dummy reference class to simulate a Reference object with identifiers."""

    def __init__(self, identifiers) -> None:
        """
        Initialize the DummyReference with a list of identifiers.

        Args:
            identifiers (_type_): A list of DummyIdentifier objects.

        """
        self.identifiers = identifiers


def test_invalid_doi_error():
    bad_doi = "bad_doi"
    assert not validate_doi(bad_doi)


def test_get_doi_from_reference_success():
    # Patch validate_doi to return True for the first identifier
    test_good_doi = "10.1000/xyz123"
    dummy_id = DummyIdentifier(test_good_doi)
    dummy_ref = DummyReference([dummy_id])

    with patch("app.utils.validate_doi", return_value=True):
        assert get_doi_from_reference(dummy_ref) == test_good_doi


@pytest.mark.parametrize(
    "test_full_url_doi",
    [
        "https://doi.org/10.1000/xyz123",
        "http://doi.org/10.1000/xyz123",
        "10.1000/xyz123",
        "10.1000/xyz123/abc",
    ],
)
def test_get_valid_doi_from_full_url_success(test_full_url_doi):
    """Test that we can extract a DOI from a full URL."""
    assert validate_doi(
        test_full_url_doi
    ), "Expect this list of valid DOIs to be valid."


@pytest.mark.parametrize(
    "test_full_url_doi",
    [
        "https://doi.org/foo",
        "http://doi.org/bar",
        "baz/123",
    ],
)
def test_get_invalid_doi_from_full_url_fails_properly(test_full_url_doi):
    """Test that we can extract a DOI from a full URL."""
    assert not validate_doi(
        test_full_url_doi
    ), "Expect this list of invalid DOIs to be evaluated as invalid."


def test_get_doi_from_reference_missing_doi_error():
    error_message = "No DOI found for reference"
    test_id = uuid4()
    test_reference = Reference(
        id=test_id,
        identifiers=[
            {
                "identifier": "not_a_doi",
                "identifier_type": "other",
                "other_identifier_name": "test_identifier",
            }
        ],
    )
    with pytest.raises(MissingDOIError) as expected_error:
        get_doi_from_reference(test_reference)
    assert error_message in str(expected_error.value)


def test_validate_doi_false_for_non_string():
    assert not validate_doi(12345)
    assert not validate_doi(None)
    assert not validate_doi(["10.1000/xyz123"])


def test_validate_doi_false_for_string():
    assert not validate_doi("foo")
    assert not validate_doi("10.000/bar")


def test_validate_doi_success():
    assert validate_doi("10.1177/02633957231191445")


def test_get_version_number_from_pyproject_success(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
        [project]
        name = "fetch-abstracts-robot"
        version = "1.2.3"
        """
    )
    version = get_version_number_from_pyproject(str(pyproject))
    assert version == "1.2.3"


def test_get_version_number_from_pyproject_missing_file():
    with pytest.raises(FileNotFoundError):
        get_version_number_from_pyproject("nonexistent.toml")


def test_get_version_number_from_pyproject_missing_section(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.other]\nfoo = 'bar'\n")
    with pytest.raises(KeyError):
        get_version_number_from_pyproject(str(pyproject))


def test_get_version_number_from_pyproject_missing_key(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nname = 'fetch-abstracts-robot'\n")
    with pytest.raises(KeyError):
        get_version_number_from_pyproject(str(pyproject))
