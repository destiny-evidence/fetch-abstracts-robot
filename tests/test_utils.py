"""tests for functions in app/utils.py."""

from unittest.mock import MagicMock, patch

import pytest

from app.utils import (
    InvalidDOIError,
    MissingDOIError,
    get_doi_from_reference,
    get_version_number_from_pyproject,
    validate_doi,
)


def test_invalid_doi_error():
    error_msg = "bad_doi"
    with pytest.raises(InvalidDOIError):
        raise InvalidDOIError(error_msg)


def test_missing_doi_error():
    error_msg = "missing_doi"
    with pytest.raises(MissingDOIError):
        raise MissingDOIError(error_msg)


def test_validate_doi_false_for_non_string():
    assert not validate_doi(12345)
    assert not validate_doi(None)
    assert not validate_doi(["10.1000/xyz123"])


def test_validate_doi_false_for_string():
    assert not validate_doi("foo")
    assert not validate_doi("10.000/bar")


def test_validate_doi_success():
    assert validate_doi("10.1177/02633957231191445")


def test_get_doi_from_reference_success(monkeypatch):
    # Patch validate_doi to return True for the first identifier
    class DummyIdentifier:
        def __init__(self, identifier):
            self.identifier = identifier

    class DummyReference:
        def __init__(self, identifiers):
            self.identifiers = identifiers

    dummy_id = DummyIdentifier("10.1000/xyz123")
    dummy_ref = DummyReference([dummy_id])

    with patch("app.utils.validate_doi", return_value=True):
        assert get_doi_from_reference(dummy_ref) == "10.1000/xyz123"


def test_get_doi_from_reference_missing(monkeypatch):
    class DummyIdentifier:
        def __init__(self, identifier):
            self.identifier = identifier

    class DummyReference:
        def __init__(self, identifiers):
            self.identifiers = identifiers

    dummy_id = DummyIdentifier("not_a_doi")
    dummy_ref = DummyReference([dummy_id])

    with (
        patch("app.utils.validate_doi", return_value=False),
        pytest.raises(MissingDOIError),
    ):
        get_doi_from_reference(dummy_ref)


def test_get_version_number_from_pyproject_success(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
        [tool.poetry]
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
    pyproject.write_text("[tool.poetry]\nname = 'fetch-abstracts-robot'\n")
    with pytest.raises(KeyError):
        get_version_number_from_pyproject(str(pyproject))
