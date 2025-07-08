"""pyndatic models, validation and other scopus business."""

from app.data_models.generic import AbstractUnpackStrategy, APIConfig

SCOPUS_URL = "https://api.elsevier.com/content/abstract/doi"
SCOPUS_QUERY_PARAMS = {"view": "META_ABS"}

SCOPUS_BATCH_URL = "https://api.elsevier.com/content/search/scopus"
SCOPUS_BATCH_QUERY_PARAMS = {"next_cursor": "*", "view": "COMPLETE"}

SCOPUS_HEADERS = {"Accept": "application/json", "X-ELS-APIKey": ""}

SCOPUS_UNPACK_STRATEGY = AbstractUnpackStrategy(
    source="scopus",
    strategy=["abstracts-retrieval-response", "coredata", "dc:description"],
)
SCOPUS_BATCH_UNPACK_STRATEGY = AbstractUnpackStrategy(
    source="scopus_batch",
    doi_strategy=["search_results", "entry", "prism:doi"],
    strategy=["search_results", "entry", "dc:description"],
)

scopus_api_config = APIConfig(
    name="scopus",
    url=SCOPUS_URL,
    require_api_key=True,
    api_key_env_var_name="elsevier_scopus_key",  # pragma: allowlist secret
    api_key_placement="X-ELS-APIKey",  # pragma: allowlist secret
    query_params=SCOPUS_QUERY_PARAMS,
    headers=SCOPUS_HEADERS,
    unpack_strategy=SCOPUS_UNPACK_STRATEGY,
)

scopus_batch_api_config = APIConfig(
    name="scopus_batch",
    url=SCOPUS_BATCH_URL,
    require_api_key=True,
    api_key_env_var_name="elsevier_scopus_key",  # pragma: allowlist secret
    api_key_placement="X-ELS-APIKey",  # pragma: allowlist secret
    query_type="batch",
    query_params=SCOPUS_BATCH_QUERY_PARAMS,
    headers=SCOPUS_HEADERS,
    unpack_strategy=SCOPUS_UNPACK_STRATEGY,
)
