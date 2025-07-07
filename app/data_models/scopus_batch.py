"""pyndatic models, validation for scopus batch query."""

from app.data_models.generic import AbstractUnpackStrategy, APIConfig, QueryType

SCOPUS_BATCH_URL = "https://api.elsevier.com/content/search/scopus"
SCOPUS_BATCH_QUERY_PARAMS = {"next_cursor": "*", "view": "META_ABS"}


SCOPUS_BATCH_HEADERS = {"Accept": "application/json", "X-ELS-APIKey": ""}

SCOPUS_BATCH_UNPACK_STRATEGY = AbstractUnpackStrategy(
    source="scopus",
    strategy=["abstracts-retrieval-response", "coredata", "dc:description"],
)

scopus_batch_api_config = APIConfig(
    name="scopus_batch",
    url=SCOPUS_BATCH_URL,
    require_api_key=True,
    api_key_env_var_name="elsevier_scopus_key",  # pragma: allowlist secret
    api_key_placement="X-ELS-APIKey",  # pragma: allowlist secret
    query_type=QueryType.BATCH,
    query_params=SCOPUS_BATCH_QUERY_PARAMS,
    headers=SCOPUS_BATCH_HEADERS,
    unpack_strategy=SCOPUS_BATCH_UNPACK_STRATEGY,
)
