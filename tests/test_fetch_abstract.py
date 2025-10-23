"""tests for the core fetch_abstract module in app/fetch_abstract.py."""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from pydantic import AnyUrl

from app.data_models.generic import AbstractUnpackError
from app.fetch_abstract import AbstractFetcher, prepare_api_config


def test_prepare_api_config_success(
    scopus_api_config_valid_batch,
    crossref_api_config_valid_batch,
    external_api_priorities,
    test_settings,
):
    configs = [
        scopus_api_config_valid_batch,
        crossref_api_config_valid_batch,
    ]
    result = prepare_api_config(
        configs,
        test_settings,
        external_api_priority_batch=external_api_priorities["batch"],
    )
    batch_results = result["batch"]
    assert set(batch_results.keys()) == {"CROSSREF_BATCH", "SCOPUS_BATCH"}
    assert not batch_results["SCOPUS_BATCH"].unpack_strategy.clean_abstract_string
    assert batch_results["SCOPUS_BATCH"].headers["X-API-Key"] == "dummy_scopus_key"
    assert batch_results["SCOPUS_BATCH"].headers["X-Inst-Token"] == "dummy_inst_token"
    assert batch_results["CROSSREF_BATCH"].headers == {"Accept": "application/json"}
    assert batch_results["CROSSREF_BATCH"].api_key_env_var_name is None
    assert batch_results["CROSSREF_BATCH"].unpack_strategy.clean_abstract_string


def test_prepare_api_config_missing_key(
    external_api_priorities, invalid_api_config, test_settings
):
    configs = [invalid_api_config]
    result = prepare_api_config(
        configs,
        test_settings,
        external_api_priority_batch=external_api_priorities["batch"],
    )
    for value in result.values():
        assert value == {}


@pytest.mark.parametrize(
    "api_config_fixture",
    [
        {
            "batch": "scopus_api_config_valid_batch",
        },
        {
            "batch": "crossref_api_config_valid_batch",
        },
    ],
)
def test_abstract_fetcher_init_logs(request, api_config_fixture, test_settings):
    api_config_batch = request.getfixturevalue(api_config_fixture["batch"])
    with patch("app.fetch_abstract.logger") as mock_logger:
        master_api_config = prepare_api_config([api_config_batch], test_settings)
        fetcher = AbstractFetcher(master_api_config)
        mock_logger.info.assert_any_call(
            "Available external APIs in descending order of priority:"
        )
        for external_api_name in master_api_config["batch"]:
            assert external_api_name == api_config_batch.name.value.upper()
        assert fetcher.timeout == 60


@pytest.mark.parametrize(
    "api_config_fixture",
    [
        {
            "batch": "scopus_api_config_valid_batch",
        },
        {
            "batch": "crossref_api_config_valid_batch",
        },
    ],
)
def test_fetch_success(request, api_config_fixture, test_settings):
    api_config_batch = request.getfixturevalue(api_config_fixture["batch"])
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([api_config_batch], test_settings)
    )
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"foo": "bar"}

    test_url = AnyUrl("http://test")
    with patch("httpx.Client.get", return_value=mock_response) as mock_get:
        result = fetcher.fetch(test_url, {}, {})
        assert result == {"foo": "bar"}
        mock_get.assert_called_once()


@pytest.mark.parametrize(
    "api_config_fixture",
    [
        {
            "batch": "scopus_api_config_valid_batch",
        },
        {
            "batch": "crossref_api_config_valid_batch",
        },
    ],
)
def test_fetch_http_error(request, api_config_fixture, test_settings):
    api_config_batch = request.getfixturevalue(api_config_fixture["batch"])
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([api_config_batch], test_settings)
    )
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPError("fail")
    test_url = AnyUrl("http://test")
    with (
        patch("httpx.Client.get", return_value=mock_response),
        pytest.raises(httpx.HTTPError),
    ):
        fetcher.fetch(test_url, {}, {})


@pytest.mark.parametrize(
    ("api_config_fixture"),
    [
        ("scopus_api_config_valid_batch"),
    ],
)
def test_unpack_many_abstracts_success_batch_input_of_one_item(
    request, api_config_fixture, test_settings
):
    """
    Test unpacking a single abstract from the API response using a batch-type strategy.
    This now accomodates single requests that are formed as a single-item batch.
    """
    api_config = request.getfixturevalue(api_config_fixture)
    test_api_config = prepare_api_config([api_config], test_settings)
    external_api_name = api_config.name.value.upper()
    test_api_config["batch"][external_api_name].unpack_strategy.strategy = [
        "data",
        "abstract",
    ]
    test_api_config["batch"][external_api_name].unpack_strategy.doi_strategy = [
        "data",
        "doi",
    ]
    fetcher = AbstractFetcher(master_api_config=test_api_config)
    test_doi = "10.1000/xyz123"
    test_abstract = "This is the abstract."
    response_obj = {
        "data": [
            {
                "abstract": test_abstract,
                "doi": test_doi,
            }
        ]
    }
    result = fetcher.unpack_many_abstracts(
        response_obj,
        strategy=fetcher.master_api_config["batch"][external_api_name].unpack_strategy,
    )
    assert len(result) == 1
    assert result[0]["doi"] == test_doi
    assert result[0]["abstract"] == test_abstract


@pytest.mark.parametrize(
    "api_config_fixture",
    [
        "crossref_api_config_valid_batch",
    ],
)
def test_unpack_one_abstract_success_batched_single(
    request, api_config_fixture, test_settings
):
    """
    Test unpacking a single abstract from the API response.
    Uses a batched_single-type strategy.
    This now accomodates single requests that are formed as a single-item batch.
    """
    api_config = request.getfixturevalue(api_config_fixture)
    test_api_config = prepare_api_config([api_config], test_settings)
    external_api_name = api_config.name.value.upper()
    test_api_config["batch"][external_api_name].unpack_strategy.strategy = [
        "data",
        "abstract",
    ]
    test_api_config["batch"][external_api_name].unpack_strategy.doi_strategy = [
        "data",
        "doi",
    ]
    fetcher = AbstractFetcher(master_api_config=test_api_config)
    response_obj = {"data": {"abstract": "This is the abstract."}}
    external_api_name = api_config.name.value.upper()
    result = fetcher.unpack_one_abstract(
        response_obj,
        strategy=fetcher.master_api_config["batch"][external_api_name].unpack_strategy,
    )
    assert result == "This is the abstract."


def test_unpack_many_abstracts_scopus_batch_success(
    scopus_api_config_valid_batch, test_settings
):
    api_config_batch = scopus_api_config_valid_batch
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([api_config_batch], test_settings)
    )
    test_doi_one = "10.1000/xyz123"
    test_doi_two = "10.1000/xyz124"
    test_abstract_one = "This is one abstract."
    test_abstract_two = "This is another abstract."
    test_mocked_response_entry_object = [
        {"prism:doi": test_doi_one, "dc:description": test_abstract_one},
        {"prism:doi": test_doi_two, "dc:description": test_abstract_two},
    ]
    test_response_obj = {"search-results": {"entry": test_mocked_response_entry_object}}
    external_api_name = api_config_batch.name.value.upper()
    result = fetcher.unpack_many_abstracts(
        test_response_obj,
        strategy=fetcher.master_api_config["batch"][external_api_name].unpack_strategy,
    )
    assert len(result) == len(test_mocked_response_entry_object)
    assert result[0]["doi"] == test_doi_one
    assert result[1]["doi"] == test_doi_two
    assert result[0]["abstract"] == test_abstract_one
    assert result[1]["abstract"] == test_abstract_two


@pytest.mark.parametrize(
    "api_config_fixture",
    [
        "scopus_api_config_valid_batch",
        "crossref_api_config_valid_batch",
    ],
)
def test_unpack_one_abstract_keyerror(request, api_config_fixture, test_settings):
    """
    Test that a KeyError in unpacking is properly raised as an AbstractUnpackError.

    We expect distinct keys for different external APIs, so we are justified
    in using either fixture here and defining a set of generic bad keys in the test.
    """
    api_config = request.getfixturevalue(api_config_fixture)
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([api_config], test_settings)
    )
    response_obj = {"data": {"foo": "10.1000/xyz123", "bar": "A test abstract."}}
    with pytest.raises(AbstractUnpackError):
        (
            fetcher.unpack_one_abstract(
                response_obj,
                strategy=fetcher.master_api_config["batch"][
                    api_config.name.value.upper()
                ].unpack_strategy,
            ),
            "Expect that we raise a KeyError wrapped in AbstractUnpackError.",
        )


def test_traverse_non_dict_returns_none():
    # Should return None if input is not a dict
    result = AbstractFetcher._traverse("notadict", ["foo"])  # noqa: SLF001
    assert result is None


def test_traverse_missing_key_returns_none():
    # Should return None if key is missing
    d = {"foo": {"bar": 1}}
    result = AbstractFetcher._traverse(d, ["foo", "baz"])  # noqa: SLF001
    assert result is None


def test_unpack_many_abstracts_missing_doi_or_abstract(
    scopus_api_config_valid_batch, test_settings
):
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config(
            [scopus_api_config_valid_batch], test_settings
        )
    )
    # Entry missing abstract
    response_obj = {"search-results": {"entry": [{"prism:doi": "10.1000/xyz123"}]}}
    result = fetcher.unpack_many_abstracts(
        response_obj,
        strategy=fetcher.master_api_config["batch"]["SCOPUS_BATCH"].unpack_strategy,
    )
    assert result == []


def test_unpack_many_abstracts_empty_entries(
    scopus_api_config_valid_batch, test_settings
):
    """Should return empty list if entries is not a list (e.g., None or dict)."""
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config(
            [scopus_api_config_valid_batch], test_settings
        )
    )
    # entries is None
    response_obj = {"search-results": {"entry": None}}
    result = fetcher.unpack_many_abstracts(
        response_obj,
        strategy=fetcher.master_api_config["batch"]["SCOPUS_BATCH"].unpack_strategy,
    )
    assert result == []

    # entries is a dict, not a list
    response_obj = {"search-results": {"entry": {"prism:doi": "10.1000/xyz123"}}}
    result = fetcher.unpack_many_abstracts(
        response_obj,
        strategy=fetcher.master_api_config["batch"]["SCOPUS_BATCH"].unpack_strategy,
    )
    assert result == []


def test_unpack_many_abstracts_entry_missing_doi_and_abstract(
    scopus_api_config_valid_batch,
    test_settings,
):
    """Should skip entries missing both DOI and abstract."""
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config(
            [scopus_api_config_valid_batch], test_settings
        )
    )
    # Entry missing both DOI and abstract
    response_obj = {"search-results": {"entry": [{}]}}
    result = fetcher.unpack_many_abstracts(
        response_obj,
        strategy=fetcher.master_api_config["batch"]["SCOPUS_BATCH"].unpack_strategy,
    )
    assert result == []


def test_unpack_many_abstracts_with_cleaning(
    scopus_api_config_valid_batch, test_settings
):
    """
    Scopus abstracts don't get cleaned, but this tests the cleaning functionality
    over a batch input for future implementations.

    Note that crossref doesn't use a batch input in our implementation, so
    still relies on single abstract unpacking and cleaning.
    """
    api_config = scopus_api_config_valid_batch.model_copy()
    api_config.unpack_strategy.clean_abstract_string = True
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([api_config], test_settings)
    )
    # Abstract contains tags, should be cleaned
    cleaned_abstracts = ["Clean me!", "Clean me for a second time!"]
    batch1 = {
        "search-results": {
            "entry": [
                {
                    "prism:doi": "10.1000/xyz123",
                    "dc:description": f"<jats:p>{cleaned_abstracts[0]}</jats:p>",
                }
            ]
        }
    }
    batch2 = {
        "search-results": {
            "entry": [
                {
                    "prism:doi": "10.1000/xyz124",
                    "dc:description": f"<jats:p>{cleaned_abstracts[1]}</jats:p>",
                }
            ]
        }
    }
    response_obj = [batch1, batch2]
    result = fetcher.unpack_many_abstracts(
        response_obj,
        strategy=fetcher.master_api_config["batch"]["SCOPUS_BATCH"].unpack_strategy,
    )
    assert [result[i]["abstract"] for i in range(len(result))] == cleaned_abstracts


def test_unpack_many_abstracts_multiple_batches(
    scopus_api_config_valid_batch, test_settings
):
    """Should handle a list of batches as input."""
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config(
            [scopus_api_config_valid_batch], test_settings
        )
    )
    batch1 = {
        "search-results": {
            "entry": [{"prism:doi": "10.1000/xyz123", "dc:description": "A1"}]
        }
    }
    batch2 = {
        "search-results": {
            "entry": [{"prism:doi": "10.1000/xyz124", "dc:description": "A2"}]
        }
    }
    response_obj = [batch1, batch2]
    result = fetcher.unpack_many_abstracts(
        response_obj,
        strategy=fetcher.master_api_config["batch"]["SCOPUS_BATCH"].unpack_strategy,
    )
    assert len(result) == 2
    assert result[0]["doi"] == "10.1000/xyz123"
    assert result[1]["doi"] == "10.1000/xyz124"


def test_clean_abstract_string_removes_all_tags():
    raw = "<jats:p>This is a <b>test</b> abstract.</jats:p>"
    cleaned = AbstractFetcher.clean_abstract_string(raw)
    assert cleaned == "This is a test abstract."


def test_clean_abstract_string_fallback_regex():
    # invalid XML, should trigger the regex fallback
    raw = "<notclosed>This is broken"
    cleaned = AbstractFetcher.clean_abstract_string(raw)
    assert cleaned == "This is broken"


def test_process_doi_remove_url():
    raw = "https://doi.org/10.1109/pssgt64932.2025.11033854"
    cleaned = AbstractFetcher.process_doi(raw)
    assert cleaned == "10.1109/pssgt64932.2025.11033854"


def test_process_doi_tolower():
    raw = "10.1109/PSSGT64932.2025.11033854"
    cleaned = AbstractFetcher.process_doi(raw)
    assert cleaned == "10.1109/pssgt64932.2025.11033854"


def test_unpack_abstract_with_cleaning_crossref(
    crossref_api_config_valid_batch, test_settings
):
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config(
            [crossref_api_config_valid_batch], test_settings
        )
    )
    response_obj = {"message": {"abstract": "<jats:p>Clean me!</jats:p>"}}

    result = fetcher.unpack_one_abstract(
        response_obj,
        strategy=fetcher.master_api_config["batch"]["CROSSREF_BATCH"].unpack_strategy,
    )
    assert result == "Clean me!"


def test_fetch_many_abstracts_scopus_success_multiple_dois(
    scopus_api_config_valid_batch, test_settings
):
    """
    Scopus represents the pure batch request case, which we test here.

    We test multiple DOIs in one request, and chunking of requests into batches.
    """
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config(
            [scopus_api_config_valid_batch], test_settings
        )
    )
    dois = ["10.1000/xyz123", "10.1000/xyz124"]
    abstracts = ["Abstract 1", "Abstract 2"]
    mocked_fetch_response = {
        "search-results": {
            "entry": [
                {"prism:doi": f"{dois[0]}", "dc:description": abstracts[0]},
                {"prism:doi": f"{dois[1]}", "dc:description": abstracts[1]},
            ]
        }
    }
    expected_output_data = [
        {"doi": doi, "abstract": abstract}
        for doi, abstract in zip(dois, abstracts, strict=False)
    ]
    with (
        patch("app.fetch_abstract.validate_doi", return_value=True),
        patch.object(
            fetcher,
            "fetch",
            return_value=mocked_fetch_response,
        ),
    ):
        result = fetcher.fetch_many_abstracts(
            dois, scopus_api_config_valid_batch, chunk=True
        )
        assert next(result) == expected_output_data


def test_fetch_many_abstracts_crossref_success_multiple_dois(
    crossref_api_config_valid_batch, test_settings
):
    """
    Crossref represents the batched single request case, which we test here.

    We test multiple DOIs in one request, and _do not chunk_, using
    effectively multiple batches of size one.

    Args:
        crossref_api_config_valid_batch (_type_): _description_

    """
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config(
            [crossref_api_config_valid_batch], test_settings
        )
    )
    dois = ["10.1000/xyz123", "10.1000/xyz124"]
    abstracts = ["Abstract 1", "Abstract 2"]
    mocked_fetch_response = [
        {
            "message": {
                "DOI": doi,
                "abstract": abstract,
            }
        }
        for doi, abstract in zip(dois, abstracts, strict=False)
    ]

    expected_output_data = [
        [{"doi": doi, "abstract": abstract}]
        for doi, abstract in zip(dois, abstracts, strict=False)
    ]
    with (
        patch("app.fetch_abstract.validate_doi", return_value=True),
        patch.object(
            fetcher,
            "fetch",
            side_effect=[mocked_fetch_response[0], mocked_fetch_response[1]],
        ),
    ):
        result = fetcher.fetch_many_abstracts(dois, crossref_api_config_valid_batch)
        parsable_output = list(result)
        assert parsable_output == expected_output_data


def test_get_many_abstracts_single_invalid_doi(
    caplog, scopus_api_config_valid_batch, test_settings
):
    """Test fetching abstracts with a single invalid DOI mixed in with valid DOIs."""
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config(
            [scopus_api_config_valid_batch], test_settings
        )
    )
    invalid_doi = "bad-doi"
    dois = [invalid_doi, "10.1000/xyz124"]
    abstracts = ["Invalid DOI Abstract", "Valid DOI Abstract 2"]
    valid_doi_response = {
        "doi": dois[1],
        "abstract": abstracts[1],
        "source": "SCOPUS_BATCH",
    }
    mocked_fetch_response = {
        "search-results": {
            "entry": [
                {"prism:doi": f"{dois[1]}", "dc:description": abstracts[1]},
            ]
        }
    }
    with (
        patch.object(
            fetcher,
            "fetch",
            return_value=mocked_fetch_response,
        ),
        caplog.at_level("ERROR"),
    ):
        result = fetcher.get_many_abstracts_cycling_apis(dois)
        assert f"Invalid DOI {invalid_doi} provided" in caplog.text
        assert len(result) == 2, "Still expect the bad DOI to be represented in output."
        assert (
            valid_doi_response in result
        ), "Expect valid DOI to be represented in output."
        assert any(
            item["doi"] == invalid_doi and item["abstract"] is None for item in result
        )


def test_fetch_many_abstracts_http_error(
    caplog, scopus_api_config_valid_batch, test_settings
):
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config(
            [scopus_api_config_valid_batch], test_settings
        )
    )
    test_doi_list = ["10.1000/xyz123"]
    with (
        patch("app.fetch_abstract.validate_doi", return_value=True),
        patch.object(fetcher, "fetch", side_effect=httpx.HTTPError("fail")),
        caplog.at_level("ERROR"),
    ):
        response = fetcher.fetch_many_abstracts(
            test_doi_list, scopus_api_config_valid_batch, chunk=True
        )
        output = next(response)
        assert (
            "Encountered HTTPError on attempting to retrieve abstract." in caplog.text
        )
        assert (
            output == [{"doi": test_doi_list[0], "abstract": None}]
        ), "Expect that we return an appropriate result for the repository on HTTPErrors."


def test_fetch_many_abstracts_crossref_single_unpack_error(
    caplog, crossref_api_config_valid_batch, test_settings
):
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config(
            [crossref_api_config_valid_batch], test_settings
        )
    )
    test_dois_list = ["10.1000/xyz123"]
    with (
        patch("app.fetch_abstract.validate_doi", return_value=True),
        patch.object(fetcher, "fetch", return_value={"data": {}}),
        patch.object(
            fetcher,
            "unpack_one_abstract",
            side_effect=AbstractUnpackError("Test Abstract Unpack Failure"),
        ),
        caplog.at_level("WARNING"),
    ):
        result_generator = fetcher.fetch_many_abstracts(
            test_dois_list, crossref_api_config_valid_batch, chunk=True
        )
        results = next(result_generator)
        assert "Test Abstract Unpack Failure" in caplog.text
        assert (
            results == [{"doi": [test_dois_list[0]], "abstract": None}]
        ), "Expect that we return a null abstract on an unpack error for a single record."


@pytest.mark.parametrize(
    "api_config_fixture",
    [
        "scopus_api_config_valid_batch",
        "crossref_api_config_valid_batch",
    ],
)
def test_get_many_abstracts_cycling_apis_success(
    api_config_fixture, request, test_settings
):
    api_config = request.getfixturevalue(api_config_fixture)
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config([api_config], test_settings)
    )
    test_doi_list = ["10.1000/xyz123", "10.1000/xyz124", "10.1000/xyz125"]
    test_abstract_list = ["abstract text 1", "abstract text 2", "abstract text 3"]
    test_response_objects = [
        [{"doi": doi, "abstract": abstract}]
        for doi, abstract in zip(test_doi_list, test_abstract_list, strict=False)
    ]
    with patch.object(
        fetcher, "fetch_many_abstracts", return_value=(x for x in test_response_objects)
    ):
        result = fetcher.get_many_abstracts_cycling_apis(
            ["10.1000/xyz123", "10.1000/xyz124", "10.1000/xyz125"]
        )
        assert result == [item for sublist in test_response_objects for item in sublist]


def test_get_many_abstracts_cycling_apis_no_abstracts_found(
    caplog,
    mocker,
    crossref_api_config_valid_batch,
    scopus_api_config_valid_batch,
    test_settings,
):
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config(
            [crossref_api_config_valid_batch, scopus_api_config_valid_batch],
            test_settings,
        )
    )
    test_dois = ["10.1000/xyz123", "10.1000/xyz124", "10.1000/xyz125"]
    mocker.patch.object(fetcher, "fetch_many_abstracts", return_value=iter([]))
    with caplog.at_level("DEBUG"):
        null_enhancements = fetcher.get_many_abstracts_cycling_apis(test_dois)
    assert (
        "No abstracts found in CROSSREF_BATCH with query type batched_single."
        in caplog.text
    )
    assert "No abstracts found in SCOPUS_BATCH with query type batch." in caplog.text
    assert (
        f"0 abstracts retrieved of {len(test_dois)} valid DOIs requested" in caplog.text
    )

    assert len(list(null_enhancements)) == len(test_dois)
    assert all(item["abstract"] is None for item in null_enhancements)
    assert all(item["source"] is None for item in null_enhancements)
