"""module for fetching abstracts from various APIs."""

import re
from typing import Generator

import requests
from destiny_sdk.identifiers import DOIIdentifier

from app.config import Settings
from app.data_models.generic import (
    AbstractNotFoundError,
    AbstractUnpackError,
    AbstractUnpackStrategy,
    APIConfig,
    APIKeyNotPresentError,
    ExternalAPIPriority,
    external_api_priority_batch,
    external_api_priority_single,
)
from app.logger import logger
from app.utils import InvalidDOIError, validate_doi


def prepare_api_config(
    api_configs: list[APIConfig],
    settings: Settings,
    external_api_priority_single: ExternalAPIPriority = external_api_priority_single,
    external_api_priority_batch: ExternalAPIPriority = external_api_priority_batch,
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
    logger.debug(
        f"external_api_priority_single: {external_api_priority_single.priorities}"
    )
    logger.debug(
        f"external_api_priority_batch: {external_api_priority_batch.priorities}"
    )
    logger.debug(f"supplied api candidates: {', '.join(api_config_map.keys())}")

    for external_api_priority in [
        external_api_priority_single,
        external_api_priority_batch,
    ]:
        master_api_config[external_api_priority.name] = {}
        for api in external_api_priority.priorities:
            logger.debug(f"checking if {api.name} in list of available apis...")
            if api not in api_config_map:
                continue
            target_config = api_config_map[api]
            try:
                logger.debug(f"trying to find & init api key for {api.name}")
                target_config.init_api_key(settings=settings)
                master_api_config[external_api_priority.name][api.name] = target_config
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

        logger.info(
            "available external APIs - SINGLE - in descending order of priority:"
        )
        logger.info(", ".join(master_api_config["single"].keys()))
        logger.info(
            "available external APIs - BATCH - in descending order of priority:"
        )
        logger.info(", ".join(master_api_config["batch"].keys()))

    def get_one_abstract_cycling_apis(self, doi: str, *, verbose: bool = False) -> str:
        """
        retrieve one abstract, iterating through available APIs until
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
        for api in self.master_api_config[
            "single"
        ]:  # NOTE - @harryjmoss this is probably not a clean way of doing this... maybe we want to refine our master_api_config definition a little more now that it has single and batch elements.
            logger.info(f"attempting retrieval using api {api}.")
            abstract = self.fetch_one_abstract(
                doi=doi, api_config=self.master_api_config["single"][api]
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

    def fetch(
        self, url: str, params: dict, headers: dict, *, verbose: bool = False
    ) -> dict:
        """fetch a response from one of the APIs (generic)."""
        response = requests.get(
            url=url, params=params, headers=headers, timeout=self.timeout
        )
        if verbose:
            request_actual_headers = f"request headers: {response.request.headers}"
            request_url = f"request {response.request.url}"
            request_body = f"request {response.request.body}"
            response_status_code = f"status code: {response.status_code}"
            response_headers = f"headers: {response.headers}"
            response_cookies = f"cookies: {response.cookies}"

            logger.debug(request_actual_headers)
            logger.debug(request_url)
            logger.debug(request_body)

            logger.debug(response_status_code)
            logger.debug(response_headers)
            logger.debug(response_cookies)

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
            query=DOIIdentifier(identifier=doi).identifier
        )  # NOTE - will have to rework if query isn't submitted via url in other API

        logger.debug(f"fetching doi {doi} from api {api_config.name}")

        try:
            response = self.fetch(
                url=url,
                params=api_config.query_params,
                headers=api_config.headers,
                verbose=True,
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

    def fetch_many_abstracts(
        self,
        dois: list[str],
        api_config: APIConfig,
        doi_batch_size: int = 15,
        # ) -> Generator[dict]:
    ):
        """
        Fetch many abstracts from a target API given a list of DOIs.

        Args:
            dois (list[str]): List of DOIs to fetch abstracts for.
            api_config (APIConfig): API configuration object containing
                                the API details and unpack strategy.

        """
        dois = [
            DOIIdentifier(identifier=x).identifier for x in dois
        ]  # removing doi.org
        # we are still batching into sub-requests,
        # as we don't want to make our URL longer than 2000 chars.
        logger.debug(f"n incoming dois: {len(dois)}")
        chunked_dois = [
            dois[i : i + doi_batch_size] for i in range(0, len(dois), doi_batch_size)
        ]
        logger.debug(
            (
                f"chunked into sub-lists of {len(chunked_dois)} ",
                f"of {doi_batch_size} each.",
            )
        )
        for i, chunk in enumerate(chunked_dois):
            logger.debug(
                f"sending get request for chunk {i} out of {len(chunked_dois)}"
            )
            query_string = api_config.populate_query(query=chunk)
            query_params = api_config.query_params
            query_params["query"] = query_string
            try:
                yield self.fetch(
                    url=api_config.url,
                    params=query_params,
                    headers=api_config.headers,
                    verbose=True,
                )

            except requests.HTTPError as e:
                logger.error(
                    "encountered HTTPError on attempting to retrieve abstract. "
                    f"original error message: {e}"
                )
                raise

    @staticmethod
    def clean_abstract_string(abstract_string: str) -> str:
        """clean a given abstract string."""
        # we can add more stuff here later (e.g. validation)
        # but for now we just want to remove `jats` tags.
        # e.g. we could define an enum in generic.py with all
        # available cleaning methods -- or maybe here??? and
        # then associate them with an unpack strategy as required.
        logger.debug("removing jats tags from abstract string...")
        cleaned = re.sub(
            r"^<jats:p>(.*?)</jats:p>$", r"\1", abstract_string, flags=re.DOTALL
        )
        return cleaned.strip()

    def unpack_abstract(
        self,
        response_obj: dict,
        strategy: AbstractUnpackStrategy,
    ) -> str:
        """
        unpack the plain text of the abstract using an unpack strategy.

        if our `AbstractUnpackStrategy` has field `clean_abstract_string`
        set to `True`, we will run the `clean_abstract_string` method.

        Args:
            response_obj (dict): JSON response object from the API.
            strategy (AbstractUnpackStrategy): Unpack strategy to use.

        Raises:
            AbstractUnpackError: If unpacking the abstract fails.

        Returns:
            str: The plain text abstract extracted from the response object.

        """
        unpack_strategy = strategy.model_dump()["strategy"]
        clean = strategy.model_dump()["clean_abstract_string"]
        try:
            for level in unpack_strategy:
                abstract_object = response_obj[level]
                response_obj = abstract_object

            if clean:
                logger.debug("`clean_abstract_string` is True, cleaning abstract.")
                abstract_object = self.clean_abstract_string(abstract_object)

        except KeyError as e:
            error_message = "hit key error. check response "
            f"object and unpack strategy. original error message: {e}"

            raise AbstractUnpackError(error_message) from e
        if not isinstance(abstract_object, str):
            error_message = "Expected abstract to be a string."
            raise AbstractUnpackError(error_message)
        return abstract_object
