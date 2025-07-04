from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.data_models.generic import AbstractUnpackStrategy, APIConfig, ExternalAPI


def get_app() -> TestClient:
    """Get the FastAPI application instance."""
    from app.main import app

    return TestClient(app)


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
    monkeypatch.delenv("ELSEVIER_SCOPUS_KEY", "dummy_scopus_key")


@pytest.fixture
def test_client(set_test_environment_variables) -> Generator[TestClient, None, None]:
    client = get_app()
    yield client
    client.close()


@pytest.fixture
def scopus_api_config():
    return APIConfig(
        name=ExternalAPI.SCOPUS,
        url="https://api.example.com/",
        require_api_key=True,
        api_key_env_var_name="elsevier_scopus_key",
        api_key_placement="X-API-Key",
        query_params={},
        headers={"X-API-Key": ""},
        unpack_strategy=AbstractUnpackStrategy(
            source=ExternalAPI.SCOPUS, strategy=["data", "abstract"]
        ),
    )


@pytest.fixture
def wos_api_config():
    return APIConfig(
        name=ExternalAPI.WEB_OF_SCIENCE,
        url="https://api.example.com/",
        require_api_key=True,
        api_key_env_var_name="wos_key",
        api_key_placement="wos_key",
        query_params={},
        headers={"wos_key": ""},
        unpack_strategy=AbstractUnpackStrategy(
            source=ExternalAPI.WEB_OF_SCIENCE, strategy=["text", "meta", "abstract"]
        ),
    )
