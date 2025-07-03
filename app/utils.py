"""misc/utility functions for our abstract fetcher robot."""

import toml
from destiny_sdk.identifiers import DOIIdentifier, ExternalIdentifierType
from destiny_sdk.references import Reference
from pydantic import ValidationError


class InvalidDOIError(Exception):
    """custom exception to throw when DOI is invalid."""


class MissingDOIError(Exception):
    """exception for when a reference doesn't contain a DOI."""


def validate_doi(doi_string: str) -> bool:
    """
    validate a DOI string using a regular expression.

    returns `True` if valid, `False` otherwise.
    """
    if not isinstance(doi_string, str):
        return False
    try:
        DOIIdentifier(identifier=doi_string, identifier_type=ExternalIdentifierType.DOI)
        return True
    except ValidationError as e:
        return False


def get_doi_from_reference(reference: Reference) -> str:
    """extract doi from a reference obj."""
    for _id in reference.identifiers:
        if validate_doi(_id, DOIIdentifier):
            return _id.identifier
    error_message = f"No DOI found for reference {reference}"
    raise MissingDOIError(error_message)


def get_version_number_from_pyproject(
    pyproject_toml_file: str = "pyproject.toml",
    section: str = "tool.poetry",
    key: str = "version",
) -> str:
    """
    retrieve the version number from a pyproject.toml file.

    Args:
        pyproject_toml_file (str): Path to the pyproject.toml file.
        section (str): Section in the TOML file (dot-separated).
        key (str): Key to retrieve (default: "version").

    Returns:
        str: The version string.

    raises:
        KeyError: If the section or key is not found.
        FileNotFoundError: If the file does not exist.

    """
    data = toml.load(pyproject_toml_file)
    # Traverse the section path (e.g., "tool.poetry")
    section_dict = data
    for part in section.split("."):
        section_dict = section_dict[part]
    return section_dict[key]
