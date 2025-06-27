"""misc/utility functions for our abstract fetcher robot."""

import re


class InvalidDOIError(Exception):
    """custom exception to throw when DOI is invalid."""

    pass


def validate_doi(doi_string: str) -> bool:
    """
    validate a DOI string using a regular expression.

    returns `True` if valid, `False` otherwise.
    """
    pattern = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$", re.IGNORECASE)
    return bool(pattern.match(doi_string))
    return bool(pattern.match(doi_string))
