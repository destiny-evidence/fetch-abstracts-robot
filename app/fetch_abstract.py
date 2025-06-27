"""module for fetching abstracts from various APIs."""

from typing import Any

import requests

from app.config import Settings, get_settings
from app.logger import logger
from app.utils import InvalidDOIError, validate_doi
from data_models.generic import (
    AbstractNotFoundError,
    AbstractUnpackError,
    AbstractUnpackStrategy,
    APIConfig,
    APIKeyNotPresentError,
    ExternalAPIPriority,
)

settings = get_settings()


def prepare_api_config(
    external_api_priority: ExternalAPIPriority,
    api_configs: list[APIConfig],
    settings: Settings = settings,
) -> dict[str, APIConfig]:
    """
    prepare a dict of APIConfig objects, populated with API keys.

    if API keys are not present for a given API,
    this will be omited from the overall API config

    NOTE: right now, we can pass a list of APIConfigs.
    an API config will only be allowed if it's in the list of
    permitted APIs in generic.ExternalAPI.
    """
    master_api_config = {}
    api_config_map = {config.name.value: config for config in api_configs}
    logger.debug(f"external_api_priority: {external_api_priority.priorities}")
    logger.debug(f"supplied api candidates: {', '.join(api_config_map.keys())}")

    for api in external_api_priority.priorities:
        logger.debug(f"checking if {api.name} in list of available apis...")
        if api not in api_config_map:
            continue
        target_config = api_config_map[api]
        try:
            logger.debug(f"trying to find & init api key for {api.name}")
            target_config.init_api_key(settings=settings)
            master_api_config[api.name] = target_config
            logger.info(f"successfully initialised API key for {api.name}.")
        except APIKeyNotPresentError as e:
            logger.info(f"no API key for {api.name}. not populating config.")
            logger.info(f"original error message: {e}.")
            continue

    return master_api_config


class AbstractFetcher:
    """a class that handles the fetching of abstracts from target APIs."""

    timeout = 60

    def __init__(self, master_api_config: dict[str, APIConfig]) -> None:
        """init our AbstractFetcher instance."""
        self.master_api_config = master_api_config

        logger.info("available external APIs, in descending order of priority:")
        logger.info(", ".join(master_api_config.keys()))

    def get_abstract_cycling_apis(self, doi: str, verbose: bool = False) -> str:
        """
        retrieve abstract, iterating through available APIs until abstract found or options exhausted.

        Args:
            doi (str): a valid DOI to for the work for which
            we're looking for an abstract.

        Raises:
            InvalidDOIError: if DOI is not valid (see concerns
                             raised in validate_doi func)
            AbstractUnpackError: if we fail to extract abstract
                                 from response obj from API
            AbstractNotFoundError: if we fail to find an abstract
                                   despite cycling all APIs.

        Returns:
            str: plain text abstract.

        """
        logger.info(f"seeking abstract for doi: {doi}")
        for api in self.master_api_config:
            logger.info(f"attempting retrieval using api {api}.")
            abstract = self.fetch_one_abstract(
                doi=doi, api_config=self.master_api_config[api]
            )
            if abstract:
                logger.info(f"abstract retrieval through {api} was succesful.")
                if verbose:
                    logger.debug(f"abstract text: {abstract}")
                return abstract
            logger.info(f"abstract retrieval through {api} was unsuccessful. next...")

        raise AbstractNotFoundError(f"unable to find abstract for {doi}.")

    @classmethod
    def fetch(cls, url: str, params: dict, headers: dict) -> dict[Any]:
        """fetch a response from one of the APIs (generic)."""
        response = requests.get(
            url=url, params=params, headers=headers, timeout=cls.timeout
        )

        response.raise_for_status()

        return response.json()

    @classmethod
    def fetch_one_abstract(cls, doi: str, api_config: APIConfig) -> str:
        """
        fetch one abstract from a target api given an API config object.

        NOTE: we should probably consider validating whether a DOI is
        a valid DOI (regex??) -- however, looking at this here -
        https://stackoverflow.com/questions/27910/finding-a-doi-in-a-document-or-page#48524047,
        there's only a 99.3% match of using regex to validate...

        for now, it's implemented using `validate_doi`
        """
        if not validate_doi(doi):
            raise InvalidDOIError(f"doi {doi} is not a valid DOI.")
        url = api_config.populate_query(
            query=doi
        )  # NOTE - will have to rework if query isn't submitted via url in other API

        logger.debug(f"fetching doi {doi} from api {api_config.name}")

        try:
            response = cls.fetch(
                url=url,
                params=api_config.query_params,
                headers=api_config.headers,
            )
        except requests.HTTPError as e:
            logger.error(
                "encountered HTTPError on attempting to retrieve abstract. "
                f"original error message: {e}"
            )
            raise

        try:
            return cls.unpack_abstract(
                response_obj=response, strategy=api_config.unpack_strategy
            )
        except AbstractUnpackError as e:
            logger.error(
                "encountered an error unpacking the abstract. "
                f"original error messsage: {e}"
            )
            raise

        # return response

    @classmethod
    def fetch_many_abstracts(cls, dois: list[str], api_config):
        pass

    @classmethod
    def unpack_abstract(
        cls, response_obj: dict, strategy: AbstractUnpackStrategy
    ) -> str:
        """unpack the plain text of the abstract using an unpack strategy."""
        unpack_strategy = strategy.model_dump()["strategy"]
        try:
            abstract = response_obj
            for level in unpack_strategy:
                abstract = abstract[level]

            return abstract
        except KeyError as e:
            raise AbstractUnpackError(
                "hit key error. check response object and unpack strategy. "
                f"original error message: {e}"
            ) from e
