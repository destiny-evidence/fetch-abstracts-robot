"""pyndatic models, validation and other scopus business."""

from data_models.generic import AbstractUnpackStrategy, APIConfig

SCOPUS_URL = "https://api.elsevier.com/content/abstract/doi"
SCOPUS_QUERY_PARAMS = {"view": "META_ABS"}


SCOPUS_HEADERS = {"Accept": "application/json", "X-ELS-APIKey": ""}

SCOPUS_UNPACK_STRATEGY = AbstractUnpackStrategy(
    source="scopus",
    strategy=["abstracts-retrieval-response", "coredata", "dc:description"],
)

scopus_api_config = APIConfig(
    name="scopus",
    url=SCOPUS_URL,
    api_key_env_var_name="elsevier_scopus_key",  # pragma: allowlist secret
    api_key_placement="X-ELS-APIKey",  # pragma: allowlist secret
    query_params=SCOPUS_QUERY_PARAMS,
    headers=SCOPUS_HEADERS,
    unpack_strategy=SCOPUS_UNPACK_STRATEGY,
)
