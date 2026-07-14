import json

import pytest

from far.local.run import main


def test_main_happy_path(mocker, tmp_path, test_references):
    doi_list_file = tmp_path / "doi_list.txt"

    with doi_list_file.open("w") as file:
        for reference in test_references:
            file.write(f"{reference.identifiers[0].identifier}\n")

    test_abstracts_dois_dict = [
        {
            "doi": test_references[0].identifiers[0].identifier,
            "abstract": "This is test abstract 1.",
        },
        {
            "doi": test_references[1].identifiers[0].identifier,
            "abstract": "This is test abstract 2.",
        },
    ]
    mocker.patch(
        "far.fetch_abstract.AbstractFetcher.get_many_abstracts_cycling_apis",
        return_value=test_abstracts_dois_dict,
    )
    main(doi_list=doi_list_file, output_directory=tmp_path / "output")

    output_dir = tmp_path / "output"
    assert output_dir.exists()
    assert output_dir.is_dir()

    with (output_dir / "abstracts_doi_list.json").open() as file:
        output_data = json.load(file)

    assert "abstracts" in output_data
    assert len(output_data["abstracts"]) == len(test_abstracts_dois_dict)


def test_main_no_abstracts_found(mocker, caplog, tmp_path, test_references):
    doi_list_file = tmp_path / "doi_list.txt"
    expected_output_dois = [
        test_ref.identifiers[0].identifier for test_ref in test_references
    ]
    with doi_list_file.open("w") as file:
        for reference in test_references:
            file.write(f"{reference.identifiers[0].identifier}\n")

    test_empty_abstracts_dois_dict = [
        {
            "doi": test_references[0].identifiers[0].identifier,
        },
        {
            "doi": test_references[1].identifiers[0].identifier,
        },
    ]
    mocker.patch(
        "far.fetch_abstract.AbstractFetcher.get_many_abstracts_cycling_apis",
        return_value=test_empty_abstracts_dois_dict,
    )

    sys_exit_mock = mocker.patch("sys.exit", side_effect=SystemExit)

    with pytest.raises(SystemExit), caplog.at_level("CRITICAL"):
        main(doi_list=doi_list_file, output_directory=tmp_path / "output")
    assert "Error during abstract enhancement generation" in caplog.text

    output_dir = tmp_path / "output"
    expected_output_file = output_dir / "abstracts_doi_list.json"

    sys_exit_mock.assert_called_once_with(1)
    assert output_dir.exists()
    assert output_dir.is_dir()
    with expected_output_file.open() as file:
        output_data = json.load(file)

    assert "abstracts" in output_data
    assert not output_data.get("abstracts")
    assert not output_data.get("dois_with_abstracts")
    assert output_data.get("dois_without_abstracts") == expected_output_dois
