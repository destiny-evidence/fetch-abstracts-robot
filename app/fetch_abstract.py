"""module for fetching abstracts from various APIs."""

from typing import Any

import requests
from config import get_settings
from logger import logger

from data_models.generic import (
    AbstractUnpackStrategy,
    ExternalAPIPriority,
    external_api_priority,
)
from data_models.scopus import (
    SCOPUS_HEADERS,
    SCOPUS_QUERY_PARAMS,
    SCOPUS_UNPACK_STRATEGY,
)

settings = get_settings()


class AbstractFetcher:
    """a class that handles the fetching of abstracts from target APIs."""

    timeout = 60

    def __init__(
        self,
        scopus_api_key: str = settings.elsevier_scopus_key.get_secret_value(),
        wos_api_key: str = settings.web_of_science_api_key.get_secret_value(),
        api_priority: ExternalAPIPriority = external_api_priority,
    ) -> None:
        """init our AbstractFetcher instance."""
        self.scopus_api_key = scopus_api_key
        self.wos_api_key = wos_api_key
        self.api_priority = api_priority

        # NOTE - rewrite this to store the headers and params in a dict based
        # on priority and whats available.
        self.scopus_headers = SCOPUS_HEADERS if scopus_api_key else None
        if self.scopus_headers:
            self.scopus_headers["X-ELS-APIKey"] = self.scopus_api_key

        logger.info("external api service priority for retrieving abstracts:")
        logger.info(self.api_priority)

    @classmethod
    def fetch(cls, url: str, query: str, params: dict, headers: dict) -> dict[Any]:
        """fetch a response from one of the APIs (generic)."""
        params["query"] = query
        response = requests.get(
            url=url, params=params, headers=headers, timeout=cls.timeout
        )

        response.raise_for_status()

        return response.json()

    @classmethod
    def fetch_one_abstract(
        cls,
        doi: str,
    ):
        pass

    @classmethod
    def fetch_many_abstract(cls, query, params, headers):
        pass

    @classmethod
    def unpack_abstract(
        cls, response_obj: dict, strategy: AbstractUnpackStrategy
    ) -> str:
        """unpack the plain text of the abstract using an unpack strategy."""
        unpack_strategy = strategy.model_dump()["strategy"]
        abstract = response_obj
        for level in unpack_strategy:
            abstract = abstract[level]

        return abstract


"""
to do:
- figure out how to define APIConfig for an actual api, like scopus
    - where does the API key come in? --> probably in __init__ - but maybe it doesn't matter...
        - maybe we can have a pydantic method to populate this field later? 
    - where does the query come in? --> probably in the fetch_one_abstract method

- think about how we would go about retrieving several abstracts
    - what if some of them are successful, but some aren't?
    - what kind of numbers are useful? number of input DOIs, page size, etc.
    """
