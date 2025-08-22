"""Config constants for SCOPUS API; single & batch."""

from loguru import logger
from pydantic import Field

from app.config import Settings
from app.data_models.generic import (
    AbstractUnpackStrategy,
    APIConfig,
    APIKeyNotPresentError,
)

SCOPUS_URL = "https://api.elsevier.com/content/abstract/doi"
SCOPUS_QUERY_PARAMS = {"view": "META_ABS"}

SCOPUS_BATCH_URL = "https://api.elsevier.com/content/search/scopus"
SCOPUS_BATCH_QUERY_PARAMS = {"next_cursor": "*", "view": "COMPLETE"}

SCOPUS_HEADERS = {
    "Accept": "application/json",
    "X-ELS-APIKey": "",
    "X-ELS-Insttoken": "",
}

SCOPUS_UNPACK_STRATEGY = AbstractUnpackStrategy(
    source="scopus",
    strategy=["abstracts-retrieval-response", "coredata", "dc:description"],
)
SCOPUS_BATCH_UNPACK_STRATEGY = AbstractUnpackStrategy(
    source="scopus_batch",
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
        api_key = (
            getattr(settings, self.api_key_env_var_name, None)
            if self.api_key_env_var_name
            else None
        )
        inst_token = (
            getattr(settings, self.api_inst_token_env_var_name, None)
            if self.api_inst_token_env_var_name
            else None
        )
        if api_key is None:
            error_message = f"API key for {self.name} is not present in settings."
            raise APIKeyNotPresentError(error_message)
        if inst_token is None:
            error_message = (
                f"Inst token for {self.name} is not present in settings"
                " skipping header population."
            )
            logger.warning(error_message)
        self.headers[self.api_key_placement] = api_key.get_secret_value()
        self.headers[self.api_inst_token_placement] = (
            inst_token.get_secret_value() if inst_token else ""
        )


scopus_api_config = ScopusAPIConfig(
    name="scopus",
    url=SCOPUS_URL,
    require_api_key=True,
    api_key_env_var_name="elsevier_scopus_key",  # pragma: allowlist secret
    api_key_placement="X-ELS-APIKey",  # pragma: allowlist secret
    query_params=SCOPUS_QUERY_PARAMS,
    headers=SCOPUS_HEADERS,
    unpack_strategy=SCOPUS_UNPACK_STRATEGY,
)

scopus_batch_api_config = ScopusAPIConfig(
    name="scopus_batch",
    url=SCOPUS_BATCH_URL,
    require_api_key=True,
    api_key_env_var_name="elsevier_scopus_key",  # pragma: allowlist secret
    api_key_placement="X-ELS-APIKey",  # pragma: allowlist secret
    query_type="batch",
    query_params=SCOPUS_BATCH_QUERY_PARAMS,
    headers=SCOPUS_HEADERS,
    unpack_strategy=SCOPUS_BATCH_UNPACK_STRATEGY,
)
