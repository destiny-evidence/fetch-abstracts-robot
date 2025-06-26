"""generic data models and validators."""

from enum import StrEnum

from pydantic import AnyUrl, BaseModel, Field


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

    url: AnyUrl = Field(description="the url/endpoint for the given API")
    query_params: dict = Field(
        description="the query params to pass with the api call."
    )
    headers: dict = Field(description="the headers to pass with the request.")
    unpack_strategy: AbstractUnpackStrategy = Field(
        description="the unpack strategy to employ to get a plain-text abstract"
    )
