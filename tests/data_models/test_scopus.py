# ruff: noqa: E501
import pytest

from app.config import Settings
from app.data_models.generic import (
    AbstractUnpackStrategy,
    APIKeyNotPresentError,
)
from app.data_models.scopus import ScopusAPIConfig


def test_scopus_api_config_creation_success_no_inst_token(
    test_settings: Settings, caplog
):
    config = ScopusAPIConfig(
        name="scopus",
        url="https://a-test-url",
        require_api_key=True,
        api_key_env_var_name="elsevier_scopus_key",  # pragma: allowlist secret
        api_key_placement="X-API-Key",  # pragma: allowlist secret
        query_params={},
        headers={"X-API-Key": ""},
        unpack_strategy=AbstractUnpackStrategy(
            source="scopus_batch",
            doi_strategy=["search-results", "entry", "prism:doi"],
            strategy=["search-results", "entry", "dc:description"],
        ),
        api_inst_token_env_var_name=None,
        api_inst_token_placement=None,
    )

    with caplog.at_level("WARNING"):
        config.init_api_key(test_settings)

    assert any(
        "Inst token for scopus is not present in settings, skipping header population."
        in message
        for message in caplog.text.splitlines()
    )

    assert (
        config.headers[config.api_key_placement]
        == test_settings.elsevier_scopus_key.get_secret_value()
    )
    assert config.headers[config.api_inst_token_placement] == ""


def test_scopus_api_config_no_api_key(test_settings: Settings):
    config = ScopusAPIConfig(
        name="scopus",
        url="https://a-test-url",
        require_api_key=True,
        api_key_env_var_name="nonexistent_key",  # pragma: allowlist secret
        api_key_placement="X-API-Key",  # pragma: allowlist secret
        query_params={},
        headers={"X-API-Key": ""},
        unpack_strategy=AbstractUnpackStrategy(
            source="scopus_batch",
            doi_strategy=["search-results", "entry", "prism:doi"],
            strategy=["search-results", "entry", "dc:description"],
        ),
    )

    with pytest.raises(APIKeyNotPresentError) as excinfo:
        config.init_api_key(test_settings)

    assert "API key for scopus is not present in settings." in str(excinfo.value)


def test_scopus_api_config_with_valid_keys(test_settings: Settings):
    config = ScopusAPIConfig(
        name="scopus",
        url="https://a-test-url",
        require_api_key=True,
        api_key_env_var_name="elsevier_scopus_key",  # pragma: allowlist secret
        api_key_placement="X-API-Key",  # pragma: allowlist secret
        query_params={},
        headers={"X-API-Key": ""},
        unpack_strategy=AbstractUnpackStrategy(
            source="scopus_batch",
            doi_strategy=["search-results", "entry", "prism:doi"],
            strategy=["search-results", "entry", "dc:description"],
        ),
        api_inst_token_env_var_name="elsevier_scopus_inst_token",  # pragma: allowlist secret # noqa: S106
        api_inst_token_placement="X-Inst-Token",  # pragma: allowlist secret # noqa: S106
    )

    config.init_api_key(test_settings)

    assert (
        config.headers["X-API-Key"]
        == test_settings.elsevier_scopus_key.get_secret_value()
    )
    assert (
        config.headers["X-Inst-Token"]
        == test_settings.elsevier_scopus_inst_token.get_secret_value()
    )
