"""Define config for PubMed API DOI lookup and abstract retrieval."""

import tomllib
from pathlib import Path

from far.config import Settings
from far.data_models.generic import AbstractUnpackStrategy, APIConfig, QueryType
from far.providers.pubmed import fetch_abstract_by_doi


def _get_tool_name_from_pyproject() -> str | None:
    """
    Read project name from pyproject.toml.

    Allows specification of the tool for the PubMed API.

    Returns:
        str | None: The project name if found, otherwise None.

    """
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    if not pyproject_path.exists():
        return None
    with pyproject_path.open("rb") as file_handle:
        data = tomllib.load(file_handle)
    project_name = data.get("project", {}).get("name")
    if not isinstance(project_name, str):
        return None
    project_name = project_name.strip()
    return project_name if project_name else None


def get_pubmed_batch_api_config(settings: Settings) -> APIConfig:
    """
    Define and return the PubMed API configuration.

    Returns:
        APIConfig: An instance of APIConfig with the PubMed API settings.

    """
    query_params: dict[str, str] = {
        "db": "pubmed",
        "retmode": "json",
    }
    tool_name = _get_tool_name_from_pyproject()
    if tool_name:
        query_params["tool"] = tool_name
    if settings.mailto:
        query_params["email"] = str(settings.mailto)

    return APIConfig(
        name="pubmed_batch",
        url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        require_api_key=False,
        api_key_env_var_name=None,
        api_key_placement=None,
        headers={"Accept": "application/json"},
        query_type=QueryType.BATCHED_SINGLE,
        query_params=query_params,
        unpack_strategy=AbstractUnpackStrategy(
            source="pubmed_batch",
            strategy=["unused"],
        ),
        provider_fetch_hook=fetch_abstract_by_doi,
    )
