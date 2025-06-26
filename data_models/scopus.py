"""pyndatic models, validation and other scopus business"""

from enum import StrEnum

from generic import AbstractUnpackStrategy, APIConfig, ExternalAPI
from pydantic import BaseModel, Field

# class ScopusQueryParamViews(StrEnum):
#     COMPLETE = "COMPLETE"


# class ScopusQueryParams(BaseModel):
#     query: str = Field(
#         description="the query to send to the scopus API `content/search/scopus` endpoint"
#     )
#     cursor: str = Field(default="*", description="pagination cursor")
#     view: ScopusQueryParamViews = ScopusQueryParamViews.COMPLETE

SCOPUS_URL = "https://api.elsevier.com/content/abstract/doi"
SCOPUS_QUERY_PARAMS = {"query": "", "cursor": "*"}

SCOPUS_HEADERS = {"Accept": "application/json", "X-ELS-APIKey": ""}

SCOPUS_UNPACK_STRATEGY = AbstractUnpackStrategy(
    source="scopus",
    strategy=["abstracts-retrieval-response", "coredata", "dc:description"],
)

# here the Q is whether we want a new class or
# just an instance of APICOnfig, and how we then get
# that into the context of our AbstractFetcher.
# SCOPUS_API_CONFIG = APIConfig()

# class ScopusUnpackStrategy(AbstractUnpackStrategy):
#     """our unpack strategy for the scopus api."""

#     source: ExternalAPI.SCOPUS
#     strategy: list[str] = Field(
#         default=["abstracts-retrieval-response", "coredata", "dc:description"]
#     )
