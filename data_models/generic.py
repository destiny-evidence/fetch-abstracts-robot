"""generic data models and validators."""

from enum import StrEnum
from typing import Any

from pydantic import AnyUrl, BaseModel, Field, model_validator

from app.config import Settings


class APIKeyNotPresentError(Exception):
    """Raised when the required API key is not present in the settings."""

    pass


class AbstractUnpackError(Exception):
    """to raise when we fail to unpack an abstract."""

    pass


class ExternalAPI(StrEnum):
    """
    exhaustive list of permitted external APIs which we can hit to retrieve abstracts.

    new additions here will require definition of
    new pydantic models for parsing their output and new
    implementation of retrieving their output.
    """

    SCOPUS = "scopus"
    WEB_OF_SCIENCE = "web_of_science"


class ExternalAPIPriority(BaseModel):
    """sequence definition of APIs to call for any given abstract."""

    priorities: dict[ExternalAPI, int] = Field(
        ..., description="mapping of `ExternalAPIs` to their priority rank."
    )


external_api_priority = ExternalAPIPriority(
    priorities={
        ExternalAPI.SCOPUS: 1,
        ExternalAPI.WEB_OF_SCIENCE: 2,
    }
)


class AbstractUnpackStrategy(BaseModel):
    """
    when we retrieve an abstract, all we really want is the actual abstract text.

    this will be in different places for different
    APIs, so here we can stick all the sequential sub-keys we need
    to reference to find our abstract.
    """

    source: ExternalAPI
    strategy: list[str] = Field(
        description="""a list of keys to sequentially
        pass to the json response object to retrieve
        plain-text abstract"""
    )


class APIConfig(BaseModel):
    """a model of essential config required to get an abstract from an API."""

    name: ExternalAPI = Field(
        description="the name (we've given) to this external API service"
    )
    url: AnyUrl = Field(description="the url/endpoint for the given API")
    api_key_env_var_name: str = Field(
        description="the name of the environment variable/settings field "
        "which represents an api key for this api."
    )
    api_key_placement: str = Field(
        description="the dict key in `headers` where we should insert our API key."
    )
    query_params: dict = Field(
        description="the query params to pass with the api call."
    )
    headers: dict = Field(description="the headers to pass with the request.")
    unpack_strategy: AbstractUnpackStrategy = Field(
        description="the unpack strategy to employ to get a plain-text abstract"
    )

    @model_validator(mode="before")
    @classmethod
    def api_key_placement_in_headers(cls, values: dict) -> str:
        """ensure that api_key_placement is a key in the headers dict."""
        if (
            values["headers"] is not None
            and values["api_key_placement"] not in values["headers"]
        ):
            raise ValueError(
                f"api_key_placement '{values['api_key_placement']}' must be a key in the headers dict."
            )
        return values

    def init_api_key(self, settings: Settings) -> None:
        """
        populate proper request headers with API key if present.

        raises:
            APIKeyNotPresentError
        """
        api_key = getattr(settings, self.api_key_env_var_name, None)
        if api_key is None:
            raise APIKeyNotPresentError(
                f"API key for {self.name} is not present in settings"
            )
        self.headers[self.api_key_placement] = api_key.get_secret_value()

    def populate_query(self, query: str) -> None:
        """populate a query string into the query params dict."""
        # NOTE -- this will require some more refined logic to
        # enable this to work with different api configurations
        # etc - right now this is for a POC for scopus one abstract
        # retrieval only.

        self.url = f"{self.url}/{query}"
        # self.query_params["query"] = query
