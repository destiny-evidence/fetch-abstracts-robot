"""Misc/Utility functions for our abstract fetcher robot."""

from importlib.metadata import PackageNotFoundError, version

from destiny_sdk.identifiers import DOIIdentifier, ExternalIdentifierType
from destiny_sdk.references import Reference
from loguru import logger
from pydantic import ValidationError


class VersionInfoNotFoundError(Exception):
    """Custom exception to throw when version info is not found."""


class InvalidDOIError(Exception):
    """Custom exception to throw when DOI is invalid."""


class MissingDOIError(Exception):
    """Exception for when a reference doesn't contain a DOI."""


def validate_doi(doi_string: str) -> bool:
    """
    Validate a DOI string using a regular expression.

    returns `True` if valid, `False` otherwise.
    """
    valid_doi = False
    if not isinstance(doi_string, str):
        return valid_doi
    try:
        DOIIdentifier(
            identifier=doi_string, identifier_type=ExternalIdentifierType.DOI
        ).remove_doi_url(doi_string)
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


def get_version_number(package_name: str = "fetch-abstracts-robot") -> str:
    """
    Retrieve the version number of an installed package.

    Args:
        package_name (str): The name of the package to retrieve the version for.

    Returns:
        str: The version string.

    Raises:
        PackageNotFoundError: If the package is not found.

    """
    try:
        return version(package_name)
    except PackageNotFoundError as package_error:
        error_message = f"Package not found: {package_name}"
        logger.error(error_message)
        raise VersionInfoNotFoundError(error_message) from package_error
