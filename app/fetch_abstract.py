"""module for fetching abstracts from various APIs."""

import re
from collections.abc import Generator
from xml.etree.ElementTree import Element

import requests
from defusedxml.ElementTree import ParseError, fromstring
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
    Prepare a dict of APIConfig objects, populated with API keys.

    if API keys are not present for a given API,
    this will be omited from the overall API config

    NOTE: right now, we can pass a list of APIConfigs.
    an API config will only be allowed if it's in the list of
    permitted APIs in generic.ExternalAPI.

    Args:
        api_configs (list[APIConfig]): list of APIConfig objects to prepare.
        settings (Settings): application settings containing API keys.
        external_api_priority_single (ExternalAPIPriority): priority for single queries.
        external_api_priority_batch (ExternalAPIPriority): priority for batch queries.

    Returns:
        dict[str, APIConfig]: a dictionary mapping API names to their configurations.

    """
    master_api_config = {}  # type: dict
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
        logger.debug(f"building api config for {external_api_priority}")
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

    def __init__(self, master_api_config: dict, timeout: int = 60) -> None:
        """init our AbstractFetcher instance."""
        self.master_api_config = master_api_config  # type: dict
        self.timeout = timeout

        logger.info(
            "available external APIs - SINGLE - in descending order of priority:"
        )
        logger.debug(", ".join(master_api_config["single"].keys()))
        logger.info(
            "available external APIs - BATCH - in descending order of priority:"
        )
        logger.debug(", ".join(master_api_config["batch"].keys()))

    def get_one_abstract_cycling_apis(self, doi: str, *, verbose: bool = False) -> dict:
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
            dict: Dictionary containing the DOI and the abstract text,
                Contains keys "doi" and "abstract".

        """
        logger.info(f"seeking abstract for doi: {doi}")
        for api in self.master_api_config[
            "single"
        ]:  # NOTE - @harryjmoss this is probably not a clean way of doing this...
            # maybe we want to refine our master_api_config definition a little more
            # now that it has single and batch elements.
            logger.info(f"attempting retrieval using api {api}.")
            doi_abstract_dict = self.fetch_one_abstract(
                doi=doi, api_config=self.master_api_config["single"][api]
            )
            if doi_abstract_dict:
                found_message = f"abstract retrieval through {api} was successful."
                logger.info(found_message)
                if verbose:
                    logger.debug(f"abstract text: {doi_abstract_dict['abstract']}")
                return doi_abstract_dict
            not_found_message = f"Abstract retrieval through {api} was unsuccessful."
            logger.info(not_found_message)

        error_msg = f"unable to find abstract for {doi}."
        raise AbstractNotFoundError(error_msg)

    def get_many_abstracts_cycling_apis(
        self, dois: list[str], *, verbose: bool = False
    ) -> list[dict]:
        """
        Get many abstracts from a list of DOIs, cycling APIs in order of priority.

        Args:
            dois (list[str]): list of DOI strings.
            verbose (bool, optional): whether to provide very verbose logging for debug.
                                      Defaults to False.

        Returns:
            list[dict]: a list of dicts of abstracts and DOIs.

        """
        retrieved_abstracts = []
        for api in self.master_api_config["batch"]:
            api_count = 0
            chunk = True
            api_config: APIConfig = self.master_api_config["batch"][api]
            if api_config.query_type == "batched_single":
                chunk = False

            retrieved_responses = self.fetch_many_abstracts(
                dois=dois, api_config=api_config, chunk=chunk, verbose=verbose
            )
            if not retrieved_responses:
                error_message = f"""No abstracts found in {api} with\
                query type {api_config.query_type.value}.
                """
                logger.error(error_message)
                raise AbstractNotFoundError(error_message)
            for response in retrieved_responses:
                for abstract in response:
                    retrieved_abstracts.append(abstract)
                    dois.remove(abstract["doi"])
                    logger.info(
                        f'retrieved abstract for doi {abstract["doi"]}. '
                        "removing from master list."
                    )
                    api_count += 1

            logger.info(f"found {api_count} abstracts for api {api}.")
            logger.info(f"found {len(retrieved_abstracts)} total.")
            logger.info(f"remaining dois to collect: {len(dois)}")

        return retrieved_abstracts

    def fetch(
        self, url: str, params: dict, headers: dict, *, verbose: bool = False
    ) -> dict:
        """fetch a response from one of the APIs (generic)."""
        response = requests.get(
            url=url, params=params, headers=headers, timeout=self.timeout
        )
        if verbose:
            request_actual_headers = f"request headers: {response.request.headers}"
            request_url = f"request url: {response.request.url}"
            request_body = f"request body: {response.request.body!s}"
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

        logger.debug(f"response json: {response.json()}")
        return response.json()

    def fetch_one_abstract(self, doi: str, api_config: APIConfig) -> dict | None:
        """
        Fetch one abstract from a target api given an API config object.

        Args:
            doi (str): Pre-validated DOI of the work for which to fetch the abstract.
            api_config (APIConfig): API configuration object containing
                                    the API details and unpack strategy.

        Returns:
            Optional(dict): A dictionary containing the DOI and the abstract,
                or None if not found.

        """
        doi_validity = validate_doi(doi)
        if not doi_validity:
            error_message = f"invalid DOI: {doi}. please check the DOI and try again."
            logger.error(error_message)
            raise InvalidDOIError(error_message)
        url = api_config.populate_query(query=DOIIdentifier(identifier=doi).identifier)[
            "url"
        ]

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
            return {
                "doi": doi,
                "abstract": self.unpack_one_abstract(
                    response_obj=response, strategy=api_config.unpack_strategy
                ),
            }
        except AbstractUnpackError as abstract_unpack_error:
            error_message = f"""Error unpacking abstract for {doi=}\
            with API {api_config.name}."""
            error_message += f"\nOriginal error: {abstract_unpack_error}"
            logger.error(error_message)
            return None

    def fetch_many_abstracts(
        self,
        dois: list[str],
        api_config: APIConfig,
        doi_batch_size: int = 15,
        *,
        chunk: bool = False,
        verbose: bool = False,
        **kwargs: dict,
    ) -> Generator[list, None, None]:
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

        logger.debug(f"n incoming dois: {len(dois)}")
        logger.debug(f"query type: {api_config.query_type.value}")
        if chunk:
            # batching as we don't want to make our URL longer than 2000 chars.
            chunked_dois = [
                dois[i : i + doi_batch_size]
                for i in range(0, len(dois), doi_batch_size)
            ]
            dois = chunked_dois  # type: ignore[no-redef, assignment]
            logger.debug(
                (
                    f"chunked into sub-lists of {len(dois)} ",
                    f"of {doi_batch_size} each.",
                )
            )
        for i, _chunk in enumerate(dois):
            logger.debug(f"sending get request for chunk {i} out of {len(dois)}")
            url, params, headers = api_config.populate_query(query=_chunk).values()
            try:
                response = self.fetch(
                    url=url,
                    params=params,
                    headers=headers,
                    verbose=verbose,
                    **kwargs,
                )
            except requests.HTTPError as e:
                logger.error(
                    "encountered HTTPError on attempting to retrieve abstract. "
                    f"requested doi(s): {_chunk} "
                    f"original error message: {e}"
                )
                continue  # NOTE - changed this out from raise
                # if we get a 404 for a certain chunk??

            if api_config.query_type == "batched_single":
                logger.debug("yield for batched_single")
                try:
                    logger.debug(
                        self.unpack_one_abstract(
                            response_obj=response,
                            strategy=api_config.unpack_strategy,
                        )
                    )
                    yield [
                        {
                            "doi": _chunk,
                            "abstract": self.unpack_one_abstract(
                                response_obj=response,
                                strategy=api_config.unpack_strategy,
                            ),
                        }
                    ]
                except AbstractUnpackError as e:
                    logger.error(e)
                    continue

            elif api_config.query_type == "batch":
                logger.debug("yield for batch")
                yield self.unpack_many_abstracts(
                    response, strategy=api_config.unpack_strategy
                )  # @harryjmoss not sure if this will work yet?

    @staticmethod
    def clean_abstract_string(abstract_string: str) -> str:
        """
        remove all XML/JATS/HTML tags from the abstract string.

        rather than the builtin `xml` module, we leverage `defusedxml`
        which should hopefully protect us from malicious xml infecting our
        server.

        Args:
            abstract_string, str, the string of the abstract

        returns:
            the cleaned abstract string (currently still contains latex
            and newline)

        """
        logger.debug("removing xml/jats tags from abstract string...")
        try:
            # wrap in a root tag in case the input is a fragment
            wrapped = f"<root>{abstract_string}</root>"
            root = fromstring(wrapped)

            def _get_text(element: Element) -> str:
                """recursively join text and tail content."""
                text = element.text or ""
                for child in element:
                    text += _get_text(child)
                    text += child.tail or ""
                return text

            cleaned = _get_text(root)
            return cleaned.strip()

        except ParseError:
            # fallback: strip tags with regex
            cleaned = re.sub(r"<[^>]+>", "", abstract_string)
            return cleaned.strip()

    def unpack_one_abstract(
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
        logger.debug("in abstract unpack")
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
            error_message = (
                "Key not found in response object with current unpack strategy.",
                f"Original error message: {e}",
            )

            raise AbstractUnpackError(error_message) from e
        if not isinstance(abstract_object, str):
            abstract_not_string_error_message = "Expected abstract to be a string."
            raise AbstractUnpackError(abstract_not_string_error_message)
        return abstract_object

    @staticmethod
    def _traverse(nested_abstract_dict: dict, path: list[str]) -> list | str | None:
        """
        Traverse a nested dictionary using a list of keys.

        Args:
            nested_abstract_dict (dict): The nested dictionary to traverse.
            path (list[str]): A list of keys representing the path to traverse.

        Returns:
            list | str | None: A list found in the response with corresponding key, or a
            string if found in the case of individual DOIs and abstracts.
            Returns None if not found.

        """
        logger.debug(f"traversing object with path: {path}")
        for i, key in enumerate(path):
            logger.debug(
                f"level {i}: object type: {type(nested_abstract_dict)}, key: {key}"
            )
            if isinstance(nested_abstract_dict, dict):
                obj = nested_abstract_dict.get(key)
            else:
                logger.warning(
                    f"level {i}: expected dict, got {type(obj)}. returning None."
                )
                return None
            if obj is None:
                logger.warning(f"level {i}: key '{key}' not found. returning None.")
                return None
            nested_abstract_dict = obj
        return obj

    def unpack_many_abstracts(
        self, response_obj: dict | list, strategy: AbstractUnpackStrategy
    ) -> list[dict]:
        """Unpack many abstracts using strategy and doi_strategy."""
        logger.debug("Starting unpack_many_abstracts...")
        out = []
        strat = strategy.model_dump()
        abstract_path = strat["strategy"]
        doi_path = strat["doi_strategy"]
        clean = strat.get("clean_abstract_string", False)

        logger.debug(f"Abstract path: {abstract_path}")
        logger.debug(f"DOI path: {doi_path}")
        logger.debug(f"Clean abstract string: {clean}")

        # @harryjmoss not sure if this is the best
        # approach. should we instead encode this into the UnpackStrategy?
        shared_prefix = []
        for i, (a, d) in enumerate(zip(abstract_path, doi_path, strict=True)):
            logger.debug(f"Comparing abstract_path[{i}]='{a}' and doi_path[{i}]='{d}'")
            if a == d:
                shared_prefix.append(a)
            else:
                logger.debug(f"Shared prefix ends at index {i}")
                break
        logger.debug(f"Shared prefix: {shared_prefix}")

        # @harryjmoss same thing as above -- maybe here we should
        # stick this into the data model?
        abstract_suffix = abstract_path[len(shared_prefix) :]
        doi_suffix = doi_path[len(shared_prefix) :]
        logger.debug(f"abstract suffix: {abstract_suffix}")
        logger.debug(f"DOI suffix: {doi_suffix}")

        # support both list of batches and single batch
        batches = response_obj if isinstance(response_obj, list) else [response_obj]
        logger.debug(f"number of batches to process: {len(batches)}")

        for batch_idx, batch in enumerate(batches):
            logger.debug(f"processing batch {batch_idx}")
            entries = self._traverse(batch, shared_prefix)

            if not isinstance(entries, list):
                logger.warning(
                    f"batch {batch_idx}: entries is not a list. skipping batch."
                )
                continue

            logger.debug(f"batch {batch_idx}: found {len(entries)} entries.")
            for entry_idx, entry in enumerate(entries):
                logger.debug(f"processing entry {entry_idx} in batch {batch_idx}")
                doi = self._traverse(entry, doi_suffix)
                abstract = self._traverse(entry, abstract_suffix)
                logger.debug(f"entry {entry_idx}: DOI: {doi}, iabstract: {abstract}")

                if doi and abstract:
                    if clean:
                        logger.debug(f"entry {entry_idx}: cleaning abstract string.")
                        abstract = self.clean_abstract_string(str(abstract))
                    out.append({"doi": doi, "abstract": abstract})
                    logger.info(f"xtracted abstract for DOI: {doi}")

                else:
                    logger.warning(
                        f"entry {entry_idx}: missing DOI or abstract. DOI: {doi}, "
                        "abstract: {abstract}"
                    )

        logger.debug(f"total n abstracts unpacked: {len(out)}")
        return out
