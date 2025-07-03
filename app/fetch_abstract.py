"""module for fetching abstracts from various APIs."""

import requests

from app.config import Settings
from app.data_models.generic import (
    AbstractNotFoundError,
    AbstractUnpackError,
    AbstractUnpackStrategy,
    APIConfig,
    APIKeyNotPresentError,
    ExternalAPIPriority,
    external_api_priority,
)
from app.logger import logger
from app.utils import InvalidDOIError, validate_doi


def prepare_api_config(
    api_configs: list[APIConfig],
    settings: Settings,
    external_api_priority: ExternalAPIPriority = external_api_priority,
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

    def __init__(
        self, master_api_config: dict[str, APIConfig], timeout: int = 60
    ) -> None:
        """init our AbstractFetcher instance."""
        self.master_api_config = master_api_config
        self.timeout = timeout

        logger.info("available external APIs, in descending order of priority:")
        logger.info(", ".join(master_api_config.keys()))

    def get_abstract_cycling_apis(self, doi: str, *, verbose: bool = False) -> str:
        """
        retrieve abstract, iterating through available APIs until
        abstract found or options exhausted.

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
                found_message = f"abstract retrieval through {api} was successful."
                logger.info(found_message)
                if verbose:
                    logger.debug(f"abstract text: {abstract}")
                return abstract
            not_found_message = f"Abstract retrieval through {api} was unsuccessful."
            logger.info(not_found_message)

        error_msg = f"unable to find abstract for {doi}."
        raise AbstractNotFoundError(error_msg)

    def fetch(self, url: str, params: dict, headers: dict) -> dict:
        """fetch a response from one of the APIs (generic)."""
        response = requests.get(
            url=url, params=params, headers=headers, timeout=self.timeout
        )

        response.raise_for_status()

        return response.json()

    def fetch_one_abstract(self, doi: str, api_config: APIConfig) -> str:
        """
        Fetch one abstract from a target api given an API config object.

        Args:
            doi (str): Pre-validated DOI of the work for which to fetch the abstract.
            api_config (APIConfig): API configuration object containing
                                    the API details and unpack strategy.

        Returns:
            str: The plain text abstract extracted from the response object.

        """
        doi_validity = validate_doi(doi)
        if not doi_validity:
            error_message = f"invalid DOI: {doi}. please check the DOI and try again."
            logger.error(error_message)
            raise InvalidDOIError(error_message)
        url = api_config.populate_query(
            query=doi
        )  # NOTE - will have to rework if query isn't submitted via url in other API

        logger.debug(f"fetching doi {doi} from api {api_config.name}")

        try:
            response = self.fetch(
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
            return self.unpack_abstract(
                response_obj=response, strategy=api_config.unpack_strategy
            )
        except AbstractUnpackError as e:
            logger.error(
                "encountered an error unpacking the abstract. "
                f"original error messsage: {e}"
            )
            raise

    @classmethod
    def fetch_many_abstracts(cls, dois: list[str], api_config: APIConfig) -> None:
        """
        Fetch many abstracts from a target API given a list of DOIs.

        Currently not implemented.

        Args:
            dois (list[str]): List of DOIs to fetch abstracts for.
            api_config (APIConfig): API configuration object containing
                                the API details and unpack strategy.

        """

    def unpack_abstract(
        self, response_obj: dict, strategy: AbstractUnpackStrategy
    ) -> str:
        """
        Unpack the plain text of the abstract using an unpack strategy.

        Args:
            response_obj (dict): JSON response object from the API.
            strategy (AbstractUnpackStrategy): Unpack strategy to use.

        Raises:
            AbstractUnpackError: If unpacking the abstract fails.

        Returns:
            str: The plain text abstract extracted from the response object.

        """
        unpack_strategy = strategy.model_dump()["strategy"]
        try:
            for level in unpack_strategy:
                abstract_object = response_obj[level]
                response_obj = abstract_object
        except KeyError as e:
            error_message = "hit key error. check response "
            f"object and unpack strategy. original error message: {e}"

            raise AbstractUnpackError(error_message) from e
        if not isinstance(abstract_object, str):
            error_message = "Expected abstract to be a string."
            raise AbstractUnpackError(error_message)
        return abstract_object
