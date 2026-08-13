"""Config constants for SCOPUS API; single & batch."""

from loguru import logger
from pydantic import Field

from far.config import Settings
from far.provider_data_models.generic import (
    AbstractUnpackStrategy,
    APIConfig,
    APIKeyNotPresentError,
    ExternalAPI,
)

SCOPUS_URL = "https://api.elsevier.com/content/search/scopus"
SCOPUS_QUERY_PARAMS = {"next_cursor": "*", "view": "COMPLETE"}

SCOPUS_HEADERS = {
    "Accept": "application/json",
    "X-ELS-APIKey": "",
    "X-ELS-Insttoken": "",
}

SCOPUS_UNPACK_STRATEGY = AbstractUnpackStrategy(
    source=ExternalAPI.SCOPUS,
    doi_strategy=["search-results", "entry", "prism:doi"],
    strategy=["search-results", "entry", "dc:description"],
)


class ScopusAPIConfig(APIConfig):
    """
    Configuration for the SCOPUS API.

    Extends the base APIConfig to add Insttoken handling.
    """

    api_inst_token_placement: str | None = Field(
        description="Inst token for Scopus API", default="X-ELS-Insttoken"
    )
    api_inst_token_env_var_name: str | None = Field(
        description="Environment variable for Inst token",
        default="elsevier_scopus_inst_token",
    )

    def init_api_key(self, settings: Settings) -> None:
        """
        Populate proper request headers with API key if present.

        Raises:
            ApiKeyNotPresentError: If the API key is not present in settings.

        """
        logger.debug(f"initializing API key for {self.name} API")
        api_key_value = self._get_secret_setting_value(
            settings, self.api_key_env_var_name
        )
        inst_token_value = self._get_secret_setting_value(
            settings, self.api_inst_token_env_var_name
        )
        if api_key_value is None:
            error_message = f"API key for {self.name} is not present in settings."
            raise APIKeyNotPresentError(error_message)
        if inst_token_value is None:
            error_message = (
                f"Inst token for {self.name} is not present in settings"
                " skipping header population."
            )
            logger.warning(error_message)
        self.headers[self.api_key_placement] = api_key_value
        self.headers[self.api_inst_token_placement] = inst_token_value or ""


def get_scopus_batch_api_config(_: Settings) -> ScopusAPIConfig:
    """
    Define and return the Scopus batch API configuration.

    Args:
        _ (Settings): Application settings, unused.

    Returns:
        ScopusAPIConfig: The configuration for the Scopus batch API.

    """
    return ScopusAPIConfig(
        name=ExternalAPI.SCOPUS,
        url=SCOPUS_URL,
        require_api_key=True,
        api_key_env_var_name="elsevier_scopus_key",  # pragma: allowlist secret
        api_key_placement="X-ELS-APIKey",  # pragma: allowlist secret
        query_type="batch",
        query_params=SCOPUS_QUERY_PARAMS,
        headers=SCOPUS_HEADERS,
        unpack_strategy=SCOPUS_UNPACK_STRATEGY,
    )
