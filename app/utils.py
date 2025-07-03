"""misc/utility functions for our abstract fetcher robot."""

import re

from destiny_sdk.identifiers import DOIIdentifier
from destiny_sdk.references import Reference


class InvalidDOIError(Exception):
    """custom exception to throw when DOI is invalid."""


class MissingDOIError(Exception):
    """exception for when a reference doesn't contain a DOI."""


def validate_doi(doi_string: str) -> bool:
    """
    validate a DOI string using a regular expression.

    returns `True` if valid, `False` otherwise.
    """
    return isinstance(DOIIdentifier, doi_string)


def get_doi_from_reference(reference: Reference) -> str:
    """extract doi from a reference obj."""
    for _id in reference.identifiers:
        if validate_doi(_id, DOIIdentifier):
            return _id.identifier
    error_message = f"No DOI found for reference {reference}"
    raise MissingDOIError(error_message)
