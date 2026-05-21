"""Define common utilities for the local environment."""

from pathlib import Path
from uuid import uuid4

import ftfy
from destiny_sdk.identifiers import DOIIdentifier
from destiny_sdk.references import Reference
from pydantic import ValidationError

from far.logger import logger


class InvalidInputError(Exception):
    """Custom exception for invalid input data."""


def get_destiny_references(doi_input_file: Path) -> list[Reference]:
    """
    Generate a list of Reference objects from a file containing DOI strings.

    Args:
        doi_input_file (Path): A path to a file containing DOI strings, one per line.

    Returns:
        list[Reference]: A list of Reference objects created from the input DOIs.

    """
    try:
        with doi_input_file.open("r") as file:
            doi_strings = [ftfy.fix_text(line.strip()) for line in file if line.strip()]
    except OSError as invalid_input_error:
        error_message = f"File error: {invalid_input_error}"
        logger.error(error_message)
        raise InvalidInputError(error_message) from invalid_input_error
    return generate_references_from_doi(doi_strings)


def generate_references_from_doi(doi_input: list[str]) -> list[Reference]:
    """
    Generate a list of Reference objects from a list of DOI strings.

    Args:
        doi_input (list[str]): A list of DOI strings to be converted.

    Returns:
        list[Reference]: A list of Reference objects created from the input DOIs.

    """
    try:
        doi_identifiers = [DOIIdentifier(identifier=doi) for doi in doi_input]
    except ValidationError as invalid_input_error:
        error_message = f"Invalid DOI input: {invalid_input_error}"
        logger.error(error_message)
        raise InvalidInputError(error_message) from invalid_input_error

    return [
        Reference(id=uuid4(), identifiers=[doi_identifier])
        for doi_identifier in doi_identifiers
    ]
