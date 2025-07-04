"""pydantic models, validation and other business for CrossRef."""

from app.data_models.generic import AbstractUnpackStrategy, APIConfig

CROSSREF_URL = "https://api.crossref.org/works/"
CROSSREF_QUERY_PARAMS = {}  # type: dict
CROSSREF_UNPACK_STRATEGY = AbstractUnpackStrategy(
    source="crossref", clean_abstract_string=True, strategy=["message", "abstract"]
)

crossref_api_config = APIConfig(
    name="crossref",
    url=CROSSREF_URL,
    require_api_key=False,
    api_key_env_var_name=None,
    api_key_placement=None,
    query_params=CROSSREF_QUERY_PARAMS,
    unpack_strategy=CROSSREF_UNPACK_STRATEGY,
)
