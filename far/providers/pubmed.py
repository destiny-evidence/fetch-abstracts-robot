"""Define PubMed-specific retrieval logic."""

from typing import TYPE_CHECKING

import httpx
from defusedxml.ElementTree import ParseError, fromstring
from loguru import logger

if TYPE_CHECKING:
    from far.data_models.generic import APIConfig


def _make_search_request(
    client: httpx.Client,
    api_config: "APIConfig",
    search_params: dict[str, str],
    timeout: int,
) -> list[str] | None:
    """
    Make a search request to the PubMed ESearch API.

    Args:
        client (httpx.Client): The HTTP client.
        api_config (APIConfig): The API configuration.
        search_params (dict[str, str]): The search parameters.
        timeout (int): The timeout for the request.

    Returns:
        list[str] | None: A list of PubMed IDs or None if no results are found.

    """
    search_response = client.get(
        url=str(api_config.url),
        params=search_params,
        headers=api_config.headers,
        timeout=timeout,
    )
    search_response.raise_for_status()
    pubmed_id_list = search_response.json().get("esearchresult", {}).get("idlist", [])
    return pubmed_id_list or None


def _make_fetch_request(
    pmid_list: list[str],
    client: httpx.Client,
    search_params: dict[str, str],
    timeout: int,
) -> str:
    """
    Make a fetch request to the PubMed EFetch API.

    Args:
        pmid_list (list[str]): PubMed IDs to fetch abstracts for.
        client (httpx.Client): The HTTP client.
        search_params (dict[str, str]): The search parameters.
        timeout (int): The timeout for the request.

    Returns:
        str: The XML response potentially containing the abstract.

    """
    fetch_api_endpoint = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

    fetch_params: dict[str, str] = {
        "db": "pubmed",
        "id": pmid_list[0],
        "retmode": "xml",
    }
    tool = search_params.get("tool")
    if isinstance(tool, str) and tool.strip():
        fetch_params["tool"] = tool
    email = search_params.get("email")
    if isinstance(email, str) and email.strip():
        fetch_params["email"] = email
    fetch_response = client.get(
        url=fetch_api_endpoint,
        params=fetch_params,
        headers={"Accept": "application/xml"},
        timeout=timeout,
    )
    fetch_response.raise_for_status()
    return fetch_response.text


def fetch_abstract_by_doi(
    doi: str,
    api_config: "APIConfig",
    timeout: int,
) -> str | None:
    """
    Fetch a PubMed abstract by DOI using ESearch followed by EFetch.

    Args:
        doi (str): The DOI of the article for which to fetch the abstract.
        api_config (APIConfig): The API configuration for PubMed.
        timeout (int): The timeout for the HTTP requests.

    Returns:
        str | None: The retrieved abstract or None if the fetch fails.

    """
    search_params = api_config.query_params.copy()
    search_params["term"] = f"{doi}[DOI]"
    try:
        with httpx.Client(follow_redirects=True) as client:
            pubmed_id_list = _make_search_request(
                client, api_config, search_params, timeout
            )
            if not pubmed_id_list:
                logger.warning("No PubMed ID found for DOI {}", doi)
                return None
            fetch_response_text = _make_fetch_request(
                pubmed_id_list, client, search_params, timeout
            )
        abstract = extract_abstract_from_xml(fetch_response_text)

        if abstract:
            logger.debug(f"PubMed abstract fetched for DOI {doi}")

    except (httpx.HTTPError, ValueError, ParseError) as pubmed_error:
        logger.warning("Failed PubMed retrieval for DOI {}: {}", doi, pubmed_error)
        return None
    return abstract


def extract_abstract_from_xml(xml_string: str) -> str | None:
    """
    Extract and join all PubMed AbstractText nodes from EFetch XML.

    Args:
        xml_string (str): The XML string containing the abstract.

    Returns:
        str | None: The joined abstract text or None if no abstract is found.

    """
    root = fromstring(xml_string)
    abstract_nodes = root.findall(".//Abstract/AbstractText")
    abstract_parts = []
    for node in abstract_nodes:
        abstract_text = " ".join(node.itertext()).strip()
        if not abstract_text:
            continue

        section_label = node.attrib.get("Label")
        if section_label and section_label.strip():
            abstract_parts.append(f"{section_label.strip()}: {abstract_text}")
        else:
            abstract_parts.append(abstract_text)

    abstract_parts = [part for part in abstract_parts if part]
    if not abstract_parts:
        return None
    return "\n".join(abstract_parts)
