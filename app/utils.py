"""misc/utility functions for our abstract fetcher robot."""

import re

from destiny_sdk.identifiers import DOIIdentifier
from destiny_sdk.references import Reference


class InvalidDOIError(Exception):
    """custom exception to throw when DOI is invalid."""

    pass


class MissingDOIError(Exception):
    """exception for when a reference doesn't contain a DOI."""

    pass


def validate_doi(doi_string: str) -> bool:
    """
    validate a DOI string using a regular expression.

    returns `True` if valid, `False` otherwise.
    """
    pattern = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$", re.IGNORECASE)
    return bool(pattern.match(doi_string))


def get_doi_from_reference(reference: Reference) -> str:
    """extract doi from a reference obj."""
    for _id in reference.identifiers:
        if isinstance(_id, DOIIdentifier):
            return _id.identifier
    raise MissingDOIError("no DOI found for reference.")
