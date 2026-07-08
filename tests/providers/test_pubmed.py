"""Test the specific pubmed provider module in far/providers/pubmed.py."""

import httpx
import pytest

from far.fetch_abstract import AbstractFetcher, prepare_api_config
from far.providers.pubmed import extract_abstract_from_xml, fetch_abstract_by_doi


@pytest.fixture
def pubmed_abstract_text() -> str:
    """Provide a sample PubMed abstract text for testing."""
    return "Sample abstract text."


@pytest.fixture
def pubmed_valid_xml(pubmed_abstract_text) -> str:
    """Provide a valid PubMed XML string for testing."""
    return f"""
        <PubmedArticleSet>
            <PubmedArticle>
                <MedlineCitation>
                    <Article>
                        <Abstract>
                            <AbstractText>{pubmed_abstract_text}</AbstractText>
                        </Abstract>
                    </Article>
                </MedlineCitation>
            </PubmedArticle>
        </PubmedArticleSet>
        """


def test_extract_pubmed_abstract_from_xml_success(
    pubmed_valid_xml, pubmed_abstract_text
):
    result = extract_abstract_from_xml(pubmed_valid_xml)
    assert result == pubmed_abstract_text


def test_extract_pubmed_abstract_from_xml_missing_abstract():
    xml = "<PubmedArticleSet><PubmedArticle /></PubmedArticleSet>"
    result = extract_abstract_from_xml(xml)
    assert result is None, "Expected None when no abstract is found."


def test_fetch_abstract_by_doi_success(
    mocker, pubmed_api_config_valid_batch, pubmed_abstract_text, pubmed_valid_xml
):
    pubmed_api_config_valid_batch.query_params["tool"] = "fetch-abstracts-robot"
    pubmed_api_config_valid_batch.query_params["email"] = "robot@example.com"

    test_doi = "10.1000/xyz123"
    test_pmid = "123456"
    test_timeout = 1
    expected_abstract_text = pubmed_abstract_text
    expected_esearch_kwargs = {
        "url": str(pubmed_api_config_valid_batch.url),
        "params": {
            "db": "pubmed",
            "retmode": "json",
            "tool": "fetch-abstracts-robot",
            "email": "robot@example.com",
            "term": f"{test_doi}[DOI]",
        },
        "headers": pubmed_api_config_valid_batch.headers,
        "timeout": test_timeout,
    }
    expected_efetch_kwargs = {
        "url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
        "params": {
            "db": "pubmed",
            "id": test_pmid,
            "retmode": "xml",
            "tool": "fetch-abstracts-robot",
            "email": "robot@example.com",
        },
        "headers": {"Accept": "application/xml"},
        "timeout": test_timeout,
    }

    search_response = mocker.MagicMock()
    search_response.raise_for_status.return_value = None
    search_response.json.return_value = {"esearchresult": {"idlist": [test_pmid]}}

    fetch_response = mocker.MagicMock()
    fetch_response.raise_for_status.return_value = None
    fetch_response.text = pubmed_valid_xml
    expected_get_responses = [search_response, fetch_response]
    mocked_get = mocker.patch("httpx.Client.get", side_effect=expected_get_responses)

    result = fetch_abstract_by_doi(
        doi=test_doi,
        api_config=pubmed_api_config_valid_batch,
        timeout=test_timeout,
    )

    assert result == expected_abstract_text
    assert mocked_get.call_count == len(
        expected_get_responses
    ), "Expected call for fetch for search."
    _, esearch_kwargs = mocked_get.call_args_list[0]
    _, efetch_kwargs = mocked_get.call_args_list[-1]
    assert esearch_kwargs == expected_esearch_kwargs
    assert efetch_kwargs == expected_efetch_kwargs


@pytest.mark.parametrize(
    ("failure_mode", "expected_log_fragment", "expected_call_count"),
    [
        ("empty_idlist", None, 1),
        ("search", "search failed", 1),
        ("fetch", "fetch failed", 2),
        ("parse_error", "Failed PubMed retrieval", 2),
    ],
)
def test_fetch_abstract_by_doi_returns_none_on_failure_modes(
    mocker,
    caplog,
    pubmed_api_config_valid_batch,
    failure_mode,
    expected_log_fragment,
    expected_call_count,
):
    test_pmid = "123456"
    test_doi = "10.1000/xyz123"
    test_timeout = 1

    if failure_mode == "empty_idlist":
        search_response = mocker.MagicMock()
        search_response.raise_for_status.return_value = None
        search_response.json.return_value = {"esearchresult": {"idlist": []}}
        mocked_get = mocker.patch("httpx.Client.get", return_value=search_response)
    elif failure_mode == "search":
        mocked_get = mocker.patch(
            "httpx.Client.get", side_effect=httpx.HTTPError("search failed")
        )
    elif failure_mode == "fetch":
        search_response = mocker.MagicMock()
        search_response.raise_for_status.return_value = None
        search_response.json.return_value = {"esearchresult": {"idlist": [test_pmid]}}
        mocked_get = mocker.patch(
            "httpx.Client.get",
            side_effect=[search_response, httpx.HTTPError("fetch failed")],
        )
    else:
        search_response = mocker.MagicMock()
        search_response.raise_for_status.return_value = None
        search_response.json.return_value = {"esearchresult": {"idlist": [test_pmid]}}

        fetch_response = mocker.MagicMock()
        fetch_response.raise_for_status.return_value = None
        fetch_response.text = "<broken"

        mocked_get = mocker.patch(
            "httpx.Client.get", side_effect=[search_response, fetch_response]
        )

    with caplog.at_level("WARNING"):
        result = fetch_abstract_by_doi(
            doi=test_doi,
            api_config=pubmed_api_config_valid_batch,
            timeout=test_timeout,
        )

    assert result is None
    assert mocked_get.call_count == expected_call_count
    if expected_log_fragment is not None:
        assert expected_log_fragment in caplog.text


@pytest.mark.parametrize(
    ("use_chunking"),
    [
        True,
        False,
    ],
)
def test_fetch_many_abstracts_pubmed_hook_used_and_handles_chunking(
    mocker, pubmed_api_config_valid_batch, test_settings, use_chunking
):
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config(
            [pubmed_api_config_valid_batch], test_settings
        )
    )
    test_dois = ["10.1000/xyz123", "10.1000/xyz124"]
    test_abstract_responses = ["Abstract One", "Abstract Two"]
    expected_doi_abstract_response = [
        [{"doi": test_doi, "abstract": test_abstract}]
        for test_doi, test_abstract in zip(
            test_dois, test_abstract_responses, strict=False
        )
    ]
    mocked_hook = mocker.MagicMock(side_effect=test_abstract_responses)
    pubmed_api_config_valid_batch.provider_fetch_hook = mocked_hook

    results = list(
        fetcher.fetch_many_abstracts(
            test_dois,
            pubmed_api_config_valid_batch,
            chunk=use_chunking,
            doi_batch_size=len(test_abstract_responses),
        )
    )

    assert results == expected_doi_abstract_response, "Expect an abstract per DOI."
    assert len(mocked_hook.call_args_list) == len(
        test_dois
    ), "Provider hook called once for each DOI."
    first_args, first_kwargs = mocked_hook.call_args_list[0]
    second_args, second_kwargs = mocked_hook.call_args_list[1]
    assert first_kwargs == {}
    assert second_kwargs == {}
    assert first_args == (
        test_dois[0],
        pubmed_api_config_valid_batch,
        fetcher.timeout,
    ), "Args for first call should match."
    assert second_args == (
        test_dois[1],
        pubmed_api_config_valid_batch,
        fetcher.timeout,
    ), "Args for second call should match."


def test_get_many_abstracts_cycling_apis_pubmed_falls_back_to_scopus(
    mocker, pubmed_api_config_valid_batch, scopus_api_config_valid_batch, test_settings
):
    fetcher = AbstractFetcher(
        master_api_config=prepare_api_config(
            [pubmed_api_config_valid_batch, scopus_api_config_valid_batch],
            test_settings,
        )
    )

    test_doi = "10.1000/xyz123"
    test_final_returned_abstract = "Scopus abstract"
    mocked_pubmed_hook = mocker.MagicMock(return_value=None)
    pubmed_api_config_valid_batch.provider_fetch_hook = mocked_pubmed_hook

    scopus_response = {
        "search-results": {
            "entry": [
                {"prism:doi": test_doi, "dc:description": test_final_returned_abstract},
            ]
        }
    }
    mocker.patch.object(fetcher, "fetch", return_value=scopus_response)

    result = fetcher.get_many_abstracts_cycling_apis([test_doi])

    assert result == [
        {
            "doi": test_doi,
            "abstract": test_final_returned_abstract,
            "source": "SCOPUS_BATCH",
        }
    ]
    mocked_pubmed_hook.assert_called_once_with(
        test_doi,
        pubmed_api_config_valid_batch,
        fetcher.timeout,
    )
