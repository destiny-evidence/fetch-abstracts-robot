from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings


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
    yield
    monkeypatch.delenv("ENV")
    monkeypatch.delenv("DESTINY_REPOSITORY_URL")
    monkeypatch.delenv("ROBOT_ID")
    monkeypatch.delenv("ROBOT_SECRET")
    monkeypatch.delenv("ELSEVIER_SCOPUS_KEY")


@pytest.fixture
def test_client(set_test_environment_variables) -> Generator[TestClient, None, None]:
    client = TestClient(get_app())
    yield client
    client.close()


@pytest.fixture
def test_settings(set_test_environment_variables) -> Settings:
    return Settings()
