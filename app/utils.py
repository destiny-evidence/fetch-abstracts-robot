"""misc/utility functions for our abstract fetcher robot."""

import toml
from destiny_sdk.identifiers import DOIIdentifier, ExternalIdentifierType
from destiny_sdk.references import Reference
from loguru import logger
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
    valid_doi = False
    if not isinstance(doi_string, str):
        return valid_doi
    try:
        DOIIdentifier(identifier=doi_string, identifier_type=ExternalIdentifierType.DOI)
        valid_doi = True
    except ValidationError:
        error_message = "Invalid DOI: {doi_string}. Error: {invalid_doi_error}"
        logger.error(error_message)
        return valid_doi
    return valid_doi


def get_doi_from_reference(reference: Reference) -> str:
    """
    Extract DOI from a Reference object.

    Args:
        reference (Reference): The reference object containing identifiers.

    Returns:
        str: The DOI string if found.

    """
    for _id in reference.identifiers:
        if _id.identifier_type == ExternalIdentifierType.DOI:
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
