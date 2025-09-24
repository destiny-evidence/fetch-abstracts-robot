# ruff: noqa: E501, S106
import logging
from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from loguru import logger

from app.config import Settings
from app.data_models.generic import (
    AbstractUnpackStrategy,
    APIConfig,
    ExternalAPI,
    QueryType,
)
from app.data_models.scopus import ScopusAPIConfig

pytest_plugins = [
    "tests.fixtures.generic",
]


def get_app() -> FastAPI:
    """
    Return the FastAPI application instance for testing.

    Returns:
        FastAPI: The FastAPI application instance.

    """
    from app.main import app

    return app


@pytest.fixture(autouse=True)
def set_test_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    """Configure the pytest environment."""
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("DESTINY_REPOSITORY_URL", "http://localhost:8001/enhancement/")
    monkeypatch.setenv("ROBOT_ID", "e0aba318-eee9-4b4c-b503-7f72547063d8")
    monkeypatch.setenv("ROBOT_SECRET", "dummy_secret")
    monkeypatch.setenv("ELSEVIER_SCOPUS_KEY", "dummy_scopus_key")
    monkeypatch.setenv("ELSEVIER_SCOPUS_INST_TOKEN", "dummy_inst_token")
    yield
    monkeypatch.delenv("ENV")
    monkeypatch.delenv("DESTINY_REPOSITORY_URL")
    monkeypatch.delenv("ROBOT_ID")
    monkeypatch.delenv("ROBOT_SECRET")
    monkeypatch.delenv("ELSEVIER_SCOPUS_KEY")
    monkeypatch.delenv("ELSEVIER_SCOPUS_INST_TOKEN")


@pytest.fixture
def test_client(set_test_environment_variables) -> Generator[TestClient, None, None]:
    client = TestClient(get_app())
    yield client
    client.close()

@pytest.fixture
def scopus_api_config_valid_batch():
    return ScopusAPIConfig(
        name=ExternalAPI.SCOPUS_BATCH,
        url="https://api.example.com/",
        require_api_key=True,
        api_key_env_var_name="elsevier_scopus_key",  # pragma: allowlist secret
        api_key_placement="X-API-Key",  # pragma: allowlist secret
        query_type=QueryType.BATCH,
        query_params={},
        headers={"X-API-Key": ""},
        unpack_strategy=AbstractUnpackStrategy(
            source="scopus_batch",
            doi_strategy=["search-results", "entry", "prism:doi"],
            strategy=["search-results", "entry", "dc:description"],
        ),
        api_inst_token_env_var_name="elsevier_scopus_inst_token",  # pragma: allowlist secret
        api_inst_token_placement="X-Inst-Token",  # pragma: allowlist secret
    )

@pytest.fixture
def crossref_api_config_valid_batch():
    return APIConfig(
        name=ExternalAPI.CROSSREF_BATCH,
        url="https://api.example.com/",
        require_api_key=False,
        api_key_env_var_name=None,
        api_key_placement=None,
        query_type=QueryType.BATCHED_SINGLE,
        unpack_strategy=AbstractUnpackStrategy(
            source=ExternalAPI.CROSSREF_BATCH,
            clean_abstract_string=True,
            strategy=["message", "items", "abstract"],
            doi_strategy=["message", "items", "DOI"],
        ),
    )

@pytest.fixture
def test_settings(set_test_environment_variables) -> Settings:
    return Settings()


@pytest.fixture
def caplog(caplog):
    class PropogateHandler(logging.Handler):
        def emit(self, record) -> None:
            logging.getLogger(record.name).handle(record)

    handler_id = logger.add(PropogateHandler(), format="{message}")
    yield caplog
    logger.remove(handler_id)
