"""Config constants for CrossRef API; single & batch."""

from app.config import get_settings
from app.data_models.generic import AbstractUnpackStrategy, APIConfig, QueryType

settings = get_settings()

CROSSREF_URL = "https://api.crossref.org/works/"
CROSSREF_QUERY_PARAMS = {"mailto": settings.mailto}  # type: dict
CROSSREF_HEADERS = {
    "User-Agent": "destiny-project-ucl",
    "Accept": "application/vnd.crossref-api-message+json",
}
CROSSREF_UNPACK_STRATEGY = AbstractUnpackStrategy(
    source="crossref",
    clean_abstract_string=True,
    strategy=["message", "abstract"],
)

crossref_batch_api_config = APIConfig(
    name="crossref_batch",
    url=CROSSREF_URL,
    require_api_key=False,
    api_key_env_var_name=None,
    api_key_placement=None,
    headers={},
    query_type=QueryType.BATCHED_SINGLE,
    query_params=CROSSREF_QUERY_PARAMS,
    unpack_strategy=CROSSREF_UNPACK_STRATEGY,
)
