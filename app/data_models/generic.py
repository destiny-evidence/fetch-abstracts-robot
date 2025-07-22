"""Define generic data models and validators."""

from enum import StrEnum

from loguru import logger
from pydantic import AnyUrl, BaseModel, Field, model_validator

from app.config import Settings


class APIKeyNotPresentError(Exception):
    """Raised when the required API key is not present in the settings."""


class AbstractUnpackError(Exception):
    """to raise when we fail to unpack an abstract."""


class AbstractNotFoundError(Exception):
    """to raise when we fail to find an abstract."""


class ExternalAPI(StrEnum):
    """
    exhaustive list of permitted external APIs which we can hit to retrieve abstracts.

    new additions here will require definition of
    new pydantic models for parsing their output and new
    implementation of retrieving their output.
    """

    SCOPUS = "scopus"
    CROSSREF = "crossref"
    CROSSREF_BATCH = "crossref_batch"
    SCOPUS_BATCH = "scopus_batch"


class QueryType(StrEnum):
    """
    exhaustive list of permitted query types,
    e.g. `single` or `batch`.

    """

    SINGLE = "single"
    BATCH = "batch"
    BATCHED_SINGLE = "batched_single"


class ExternalAPIPriority(BaseModel):
    """priority definition of APIs to call for any given abstract."""

    name: str = Field(description="name of the api priority")
    priorities: dict[ExternalAPI, int] = Field(
        ..., description="mapping of `ExternalAPIs` to their priority rank."
    )


external_api_priority_single = ExternalAPIPriority(
    name="single",
    priorities={
        ExternalAPI.CROSSREF: 1,
        ExternalAPI.SCOPUS: 2,
    },
)

external_api_priority_batch = ExternalAPIPriority(
    name="batch",
    priorities={
        ExternalAPI.CROSSREF_BATCH: 1,
        ExternalAPI.SCOPUS_BATCH: 2,
    },
)


class AbstractUnpackStrategy(BaseModel):
    """
    when we retrieve an abstract, all we really want is the actual abstract text.

    this will be in different places for different
    APIs, so here we can stick all the sequential sub-keys we need
    to reference to find our abstract.
    """

    source: ExternalAPI
    clean_abstract_string: bool = Field(
        default=False,
        description="""a bool indicating whether
        we want to run the `clean_abstract_string` method
        on the string retrieved.
        """,
    )
    doi_strategy: list[str] | None = Field(
        default=None, description="strategy for unpacking DOI from response. optional."
    )
    strategy: list[str] | list[list] = Field(
        description="""a list of keys to sequentially
        pass to the json response object to retrieve
        plain-text abstract."""
    )


class APIConfig(BaseModel):
    """a model of essential config required to get an abstract from an API."""

    name: ExternalAPI = Field(
        description="the name (we've given) to this external API service"
    )
    url: AnyUrl = Field(description="the url/endpoint for the given API")
    require_api_key: bool = Field(
        description="indicates whether an API key is required to" "reach this API."
    )
    api_key_env_var_name: str | None = Field(
        description="the name of the environment variable/settings field "
        "which represents an api key for this api."
    )
    api_key_placement: str | None = Field(
        description="the dict key in `headers` where we should insert our API key."
    )
    query_type: QueryType = Field(
        default=QueryType.SINGLE, description="the type of query; e.g. single or batch."
    )
    query_params: dict = Field(
        default={},
        description="the query params to pass with the api call.",
    )
    headers: dict = Field(
        default={"Accept": "application/json"},
        description="the headers to pass with the request.",
    )
    unpack_strategy: AbstractUnpackStrategy = Field(
        description="the unpack strategy to employ to get a plain-text abstract"
    )

    @model_validator(mode="before")
    @classmethod
    def api_key_placement_in_headers(cls, values: dict) -> dict:
        """ensure that api_key_placement is a key in the headers dict."""
        if values["require_api_key"] and (
            values["headers"] is not None
            and values["api_key_placement"] not in values["headers"]
        ):
            error_msg = f"api_key_placement '{values['api_key_placement']}'"
            "must be in the values dict"
            raise ValueError(error_msg)
        return values

    def init_api_key(self, settings: Settings) -> None:
        """
        populate proper request headers with API key if present.

        Raises:
            APIKeyNotPresentError

        """
        if self.require_api_key:
            logger.debug(f"initializing API key for {self.name} API")
            api_key = (
                getattr(settings, self.api_key_env_var_name, None)
                if self.api_key_env_var_name
                else None
            )
            if api_key is None:
                error_msg = f"API key for {self.name} is not present in settings."
                raise APIKeyNotPresentError(error_msg)
            self.headers[self.api_key_placement] = api_key.get_secret_value()
        else:
            logger.info("API does not require an API key, skipping header population.")

    @staticmethod
    def build_query_single(doi: str, url: str) -> str:
        """
        Build a query string for QueryType.Single.

        Args:
            doi (str): a doi string
            url (str): the URL to append to.

        Returns:
            str: url+query

        """
        if url[-1] != "/":
            url += "/"
        return f"{url}{doi}"

    @staticmethod
    def build_query_batch(payload: list[str], max_array_length: int = 15) -> str:
        """
        Build a query string for QueryType.Batch.

        Args:
            payload (list): list of dois
            max_array_length (int, optional): n DOIs to concat into query string.
                                              Defaults to 15.

        Raises:
            ValueError: if

        Returns:
            str: query string

        """
        # NOTE - below is a conservative limit to ensure URL length
        # is the conventional limit of 2000 characters. we're assuming
        # a mean DOI length of 120 chars.
        if len(payload) > max_array_length:
            error_msg = (
                "array of items to query for is too long. max"
                f"n(items): {max_array_length}"
            )
            raise ValueError(error_msg)
        return " OR ".join([f"DOI({x})" for x in payload])

    def populate_query(
        self, query: str | list[str], max_array_length: int = 15
    ) -> dict:
        """
        Populate a query string into the query params dict.

        Args:
            query (str | list[str]): the body of the query - currently a doi or
                                     list of dois.
            max_array_length (int, optional): max number of identifiers to
                                              build the query from. Defaults to 15.

        Raises:
            TypeError
            ValueError

        Returns:
            dict: a dictionary containing the url, query_params, and headers.
                   All passed to the http request for retrieving an
                   abstract given target query and APIConfig.

        """
        if self.query_type == QueryType.SINGLE:
            if not isinstance(query, str):
                error_msg = "query_type `single` requires a `str` type query."
                raise TypeError(error_msg)
            url = self.build_query_single(doi=query, url=self.url.encoded_string())
            return {
                "url": url,
                "query_params": self.query_params,
                "headers": self.headers,
            }

        # we can add more configurations here...
        if self.query_type == QueryType.BATCH:
            if not isinstance(query, list):
                error_msg = "query_type `batch` requires a `list` type query."
                raise TypeError(error_msg)
            query_field = self.build_query_batch(
                payload=query, max_array_length=max_array_length
            )
            params = self.query_params.copy()
            params["query"] = query_field
            return {"url": self.url, "query_params": params, "headers": self.headers}

        if self.query_type == QueryType.BATCHED_SINGLE:
            if not isinstance(query, str):
                error_msg = "query_type `single` requires a `str` type query."
                raise TypeError(error_msg)
            url = self.build_query_single(doi=query, url=self.url.encoded_string())
            return {
                "url": url,
                "query_params": self.query_params,
                "headers": self.headers,
            }

        error_msg = (
            "unable to format query. ensure correct specification ",
            "of query and query type.",
        )
        raise ValueError(error_msg)
