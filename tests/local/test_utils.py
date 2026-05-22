from pathlib import Path

import pytest

from far.local.utils import (
    InvalidInputError,
    generate_references_from_doi,
    get_destiny_references,
)


def test_get_destiny_references_valid_input(tmp_path, test_references):
    doi_list_file = tmp_path / "doi_list.txt"
    with doi_list_file.open("w") as file:
        for reference in test_references:
            file.write(f"{reference.identifiers[0].identifier}\n")

    references = get_destiny_references(doi_list_file)
    assert len(references) == len(test_references)
    for reference, test_reference in zip(references, test_references, strict=False):
        assert (
            reference.identifiers[0].identifier
            == test_reference.identifiers[0].identifier
        )


def test_get_destiny_references_handles_byte_order_mark_in_dois(
    tmp_path, test_references
):
    doi_list_file = tmp_path / "doi_list.txt"
    with doi_list_file.open("w", encoding="utf-8-sig") as file:
        for reference in test_references:
            file.write(f"\ufeff{reference.identifiers[0].identifier}\n")

    references = get_destiny_references(doi_list_file)
    assert len(references) == len(test_references)
    for reference, test_reference in zip(references, test_references, strict=False):
        assert (
            reference.identifiers[0].identifier
            == test_reference.identifiers[0].identifier
        )


def test_get_destiny_references_invalid_input_error(caplog, mocker, tmp_path):
    invalid_doi_list_file = tmp_path / "invalid_doi_list.txt"
    with invalid_doi_list_file.open("w") as file:
        file.write("invalid_doi_1\n")
        file.write("invalid_doi_2\n")

    mocker.patch.object(Path, "open", side_effect=OSError("File not found"))

    with pytest.raises(InvalidInputError), caplog.at_level("ERROR"):
        get_destiny_references(invalid_doi_list_file)

    assert "File error: File not found" in caplog.text


def test_generate_references_from_doi_valid_input(test_dois):
    references = generate_references_from_doi(test_dois)
    assert len(references) == len(test_dois)
    for reference, test_doi in zip(references, test_dois, strict=False):
        assert reference.identifiers[0].identifier == test_doi


def test_generate_references_from_doi_invalid_input(caplog, test_dois):
    invalid_dois = ["invalid_doi_1", "invalid_doi_2"]
    with pytest.raises(InvalidInputError), caplog.at_level("ERROR"):
        generate_references_from_doi(invalid_dois)

    assert "Invalid DOI input" in caplog.text
