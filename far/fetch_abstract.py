"""
Core module containing the `AbstractFetcher` class to get abstracts
from various APIs.
"""

import re
from collections.abc import Generator
from xml.etree.ElementTree import Element

import httpx
from defusedxml.ElementTree import ParseError, fromstring
from destiny_sdk.identifiers import DOIIdentifier
from loguru import logger
from pydantic import AnyUrl

from far.config import Settings
from far.data_models.generic import (
    AbstractUnpackError,
    AbstractUnpackStrategy,
    APIConfig,
    APIKeyNotPresentError,
    ExternalAPIPriority,
    external_api_priority_batch,
)
from far.utils import InvalidDOIError, validate_doi


class FetchAbstractError(Exception):
    """Custom exception for errors occurring during abstract fetching."""


def prepare_api_config(
    api_configs: list[APIConfig],
    settings: Settings,
    external_api_priority_batch: ExternalAPIPriority = external_api_priority_batch,
) -> dict[str, APIConfig]:
    """
    Prepare a dict of APIConfig objects, populated with API keys.

    If API keys are not present for a given API,
    this will be omitted from the overall API config.

    NOTE: Right now, we can pass a list of APIConfigs.
    An API config will only be allowed if it's in
    the list of permitted APIs in generic.ExternalAPI.

    Args:
        api_configs (list[APIConfig]): list of APIConfig objects to prepare.
        settings (Settings): application settings containing API keys.
        external_api_priority_batch (ExternalAPIPriority): priority for batch queries.

    Returns:
        dict[str, APIConfig]: a dictionary mapping API names to their configurations.

    """
    master_api_config = {}  # type: dict
    api_config_map = {config.name.value: config for config in api_configs}
    logger.debug(
        f"external_api_priority_batch: {external_api_priority_batch.priorities}"
    )
    logger.debug(f"supplied api candidates: {', '.join(api_config_map.keys())}")

    for external_api_priority in [
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
            except APIKeyNotPresentError as missing_api_key_error:
                logger.info(f"no API key for {api.name}. not populating config.")
                logger.info(f"original error message: {missing_api_key_error}.")
                continue

    return master_api_config


class AbstractFetcher:
    """
    Handles the fetching of abstracts from target APIs. Can fetch either a `single`
    abstract, or a `batch` of abstracts.
    Single abstracts are treated as a batch of one.

    Will _cycle_ through available API configurations
    in order to retrieve abstracts by DOI.
    Will unpack and, if required, clean abstract.
    """

    def __init__(self, master_api_config: dict, timeout: int = 60) -> None:
        """
        Init our AbstractFetcher instance.

        Args:
            master_api_config (dict): retrieved from `prepare_api_config`
                using all provided API configs.
            timeout (int, optional): Network timeout. Defaults to 60.

        """
        self.master_api_config = master_api_config  # type: dict
        self.timeout = timeout

        logger.info("Available external APIs in descending order of priority:")
        logger.info(", ".join(master_api_config["batch"].keys()))

    @staticmethod
    def process_doi(doi: DOIIdentifier | str) -> str:
        """
        Validate a DOI and return the DOI string in lowercase.

        Args:
            doi (DOIIdentifier | str): DOI to process.

        Returns:
            str: Validated DOI string in lowercase.

        """
        if isinstance(doi, DOIIdentifier):
            return doi.identifier.lower()
        try:
            doi_string = validate_doi(doi)
            return doi_string.lower()
        except InvalidDOIError as invalid_doi_error:
            logger.error(
                f"Invalid DOI {doi} provided."
                f"Original error message: {invalid_doi_error}"
            )
            raise

    def get_many_abstracts_cycling_apis(
        self, input_dois: list[str], *, verbose: bool = False
    ) -> list[dict]:
        """
        Get many abstracts from a list of DOIs, cycling APIs in order of priority.

        Args:
            input_dois (list[str]): Input list of DOIs, as strings.
            verbose (bool, optional): whether to provide very verbose logging for debug.
                                      Defaults to False.

        Returns:
            list[dict]: a list of dicts of abstracts and DOIs.

        """
        dois = []
        for doi in input_dois:
            try:
                doi_string = self.process_doi(doi)
                dois.append(doi_string)
            except InvalidDOIError as invalid_doi_error:
                logger.error(f"Invalid DOI found: {invalid_doi_error}")
                continue
        input_dois = [doi.lower() for doi in input_dois if doi not in dois]

        invalid_doi_response = [
            {"doi": doi, "abstract": None, "source": None} for doi in input_dois
        ]

        references_provided = len(dois)
        retrieved_abstracts = []
        for api in self.master_api_config["batch"]:
            if len(dois) == 0:
                logger.info("All abstracts retrieved, breaking API cycle.")
                break
            logger.info(f"Fetching abstracts from API: {api}")
            api_count = 0
            chunk = True
            api_config: APIConfig = self.master_api_config["batch"][api]
            if api_config.query_type == "batched_single":
                chunk = False
            dois_to_process = dois.copy()
            retrieved_responses = self.fetch_many_abstracts(
                dois=dois_to_process,
                api_config=api_config,
                chunk=chunk,
                verbose=verbose,
            )
            found_responses = False
            for response in retrieved_responses:
                found_responses = True
                logger.debug(f"Response: {response}")
                for enhancement_dict in response:
                    enhancement_dict["source"] = api
                    logger.debug(f"Enhancement dict: {enhancement_dict}")
                    empty_abstract: bool = enhancement_dict.get("abstract") is None
                    if not empty_abstract:
                        retrieved_abstracts.append(enhancement_dict)
                        doi_to_remove = enhancement_dict.get("doi")
                        logger.info(f"Abstract hit:{doi_to_remove} from {api=}.")
                        try:
                            dois.remove(self.process_doi(doi_to_remove))
                            api_count += 1
                        except ValueError:
                            logger.warning(
                                f"DOI {doi_to_remove} not in remaining list "
                                "(may have been retrieved by a previous API)."
                            )
            if not found_responses:
                error_message = (
                    f"No abstracts found in {api} with"
                    f" query type {api_config.query_type.value}."
                )
                logger.error(error_message)

            logger.debug(f"Found {api_count} abstracts for api {api}.")
            logger.info(f"Found {len(retrieved_abstracts)} total from valid DOIs.")
            logger.info(f"Remaining valid DOIs to collect abstracts: {len(dois)}")

        logger.info(
            f"{len(retrieved_abstracts)} abstracts"
            f" retrieved of {references_provided} valid DOIs requested."
        )
        logger.info(f"{len(input_dois)} invalid DOIs provided.")
        if len(dois) > 0:
            logger.info(f"Abstracts not retrieved for {len(dois)} valid DOIs.")
        abstracts_not_found = [
            {"doi": doi, "abstract": None, "source": None} for doi in dois
        ]
        retrieved_abstracts.extend(invalid_doi_response)
        retrieved_abstracts.extend(abstracts_not_found)

        return retrieved_abstracts

    def fetch(
        self, url: AnyUrl, params: dict, headers: dict, *, verbose: bool = False
    ) -> dict:
        """
        Fetch a response from one of the APIs (generic).

        Args:
            url (AnyUrl): The URL to fetch from.
            params (dict): Query parameters to include in the request.
            headers (dict): Headers to include in the request.
            verbose (bool, optional): Whether to provide very verbose logging for debug.
                                      Defaults to False.

        Returns:
            dict: The JSON response from the API.

        Raises:
            httpx.HTTPStatusError: If an HTTP error occurs during the request.

        """
        client = httpx.Client(follow_redirects=True)
        response = client.get(
            url=str(url), params=params, headers=headers, timeout=self.timeout
        )
        if verbose:
            try:
                request_actual_headers = f"request headers: {response.request.headers}"
                request_url = f"request url: {response.request.url}"
                request_body = f"request body: {response.request.content!s}"
                response_status_code = f"status code: {response.status_code}"
                response_headers = f"headers: {response.headers}"
                response_cookies = f"cookies: {response.cookies}"

                logger.debug(request_actual_headers)
                logger.debug(request_url)
                logger.debug(request_body)

                logger.debug(response_status_code)
                logger.debug(response_headers)
                logger.debug(response_cookies)
            except AttributeError as attribute_error:
                logger.error(
                    f"AttributeError when trying to log verbose httpx info: "
                    f"{attribute_error}"
                )

        response.raise_for_status()

        logger.debug(f"response json: {response.json()}")
        return response.json()

    def fetch_many_abstracts(
        self,
        dois: list[str],
        api_config: APIConfig,
        doi_batch_size: int = 15,
        *,
        chunk: bool = False,
        verbose: bool = False,
        **kwargs: dict,
    ) -> Generator[list]:
        """
        Fetch many abstracts from a target API given a list of DOIs.

        Args:
            dois (list[str]): List of DOIs to fetch abstracts for.
            api_config (APIConfig): API configuration object containing
                                    the API details and unpack strategy.
            doi_batch_size (int, optional): Number of DOIs to batch together
                                        in a single request. Defaults to 15.
            chunk (bool, optional): Whether to chunk the DOIs into batches.
                                    Defaults to False.
            verbose (bool, optional): Whether to provide very verbose logging for debug.
                                      Defaults to False.
            **kwargs: Additional keyword arguments to pass to the `fetch` method.

        """
        logger.debug(f"{len(dois)} incoming dois")
        logger.debug(f"Query type: {api_config.query_type.value}")

        if chunk:
            # batching as we don't want to make our URL longer than 2000 chars.
            chunked_dois = [
                dois[i : i + doi_batch_size]
                for i in range(0, len(dois), doi_batch_size)
            ]
            dois = chunked_dois  # type: ignore[no-redef, assignment]
            logger.debug(
                f"Chunked into {len(dois)} sublists of max {doi_batch_size} each."
            )
        for i, _chunk in enumerate(dois):
            logger.debug(f"Sending get request for chunk {i + 1} out of {len(dois)}")
            logger.debug(f"Chunk contains: {_chunk}")

            if api_config.provider_fetch_hook is not None:
                doi_queries = _chunk if isinstance(_chunk, list) else [_chunk]
                for doi_query in doi_queries:
                    abstract = api_config.provider_fetch_hook(
                        doi_query,
                        api_config,
                        self.timeout,
                    )
                    yield [{"doi": doi_query, "abstract": abstract}]
                continue

            query_result = api_config.populate_query(query=_chunk)

            logger.trace(f"Query result: {query_result}")
            url = query_result.get("url", "")
            params = query_result.get("query_params", {})
            headers = query_result.get("headers", {})

            try:
                response = self.fetch(
                    url=url,
                    params=params,
                    headers=headers,
                    verbose=verbose,
                    **kwargs,
                )
            except httpx.HTTPError as http_error:
                logger.error(
                    "Encountered HTTPError on attempting to retrieve abstract. "
                    f"requested doi(s): {_chunk} "
                    f"original error message: {http_error}"
                )
                if isinstance(_chunk, list):
                    yielded_object = [{"doi": doi, "abstract": None} for doi in _chunk]
                else:
                    yielded_object = [{"doi": _chunk, "abstract": None}]
                yield yielded_object
            if api_config.query_type == "batched_single":
                logger.debug("yield for batched_single")
                try:
                    unpacked_abstract = self.unpack_one_abstract(
                        response_obj=response,
                        strategy=api_config.unpack_strategy,
                    )
                    logger.debug(unpacked_abstract)
                    yield [
                        {
                            "doi": _chunk,
                            "abstract": unpacked_abstract,
                        }
                    ]
                except AbstractUnpackError as abstract_unpack_error:
                    error_message = (
                        f"Error unpacking abstract for DOI {_chunk} "
                        f"using API {api_config.name.value}"
                        f": {abstract_unpack_error}"
                    )
                    logger.warning(error_message)
                    logger.warning("It is likely that no abstract is present.")
                    yield [{"doi": _chunk, "abstract": None}]

            elif api_config.query_type == "batch":
                logger.debug("yield for batch")
                yield self.unpack_many_abstracts(
                    response, strategy=api_config.unpack_strategy
                )

    @staticmethod
    def clean_abstract_string(abstract_string: str) -> str:
        """
        Remove all XML/JATS/HTML tags from the abstract string.

        Rather than the builtin `xml` module, we leverage `defusedxml`
        which should hopefully protect us from malicious xml.

        Args:
            abstract_string (str): The abstract string to clean.

        Returns:
            The cleaned abstract string (currently still contains latex
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
        Unpack the plain text of the abstract using an unpack strategy.

        If our `AbstractUnpackStrategy` has field `clean_abstract_string`
        set to `True`, we will run the `clean_abstract_string` method.

        Args:
            response_obj (dict): JSON response object from the API.
            strategy (AbstractUnpackStrategy): Unpack strategy to use.

        Returns:
            str: The plain text abstract extracted from the response object.

        Raises:
            AbstractUnpackError: If unpacking the abstract fails.

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

        except KeyError as missing_key_error:
            error_message = (
                "Key not found in response object with current unpack strategy.",
                f"Key not found: {missing_key_error}",
            )
            raise AbstractUnpackError(error_message) from missing_key_error
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
                try:
                    warning_msg = (
                        f"level {i}: expected dict, got {type(obj)}. returning None."
                    )
                except NameError:
                    warning_msg = (
                        "level {i}: expected dict, got.",
                        f"{type(nested_abstract_dict)}returning None.",
                    )
                logger.warning(warning_msg)
                return None
            if obj is None:
                obj_is_none_warning_msg = (
                    f"level {i}: key '{key}' not found. returning None."
                )
                logger.warning(obj_is_none_warning_msg)
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

        if doi_path is None:
            logger.error(
                "doi_strategy is None in unpack strategy; cannot unpack many abstracts."
            )
            return []

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
            logger.debug(f"processing batch {batch_idx + 1} of {len(batches)}")
            entries = self._traverse(batch, shared_prefix)

            if not isinstance(entries, list):
                logger.warning(
                    f"batch {batch_idx}: entries is not a list. skipping batch."
                )
                continue

            logger.debug(f"batch {batch_idx + 1}: found {len(entries)} entries.")
            for entry_idx, entry in enumerate(entries):
                logger.debug(
                    f"processing entry {entry_idx + 1} in batch {batch_idx + 1}"
                )
                doi = self._traverse(entry, doi_suffix)
                abstract = self._traverse(entry, abstract_suffix)
                logger.debug(f"entry {entry_idx + 1}: DOI: {doi}, abstract: {abstract}")

                if doi and abstract:
                    if clean:
                        logger.debug(f"entry {entry_idx}: cleaning abstract string.")
                        abstract = self.clean_abstract_string(str(abstract))
                    out.append({"doi": doi, "abstract": abstract})
                    logger.info(f"Extracted abstract for DOI: {doi}")

                else:
                    logger.warning(
                        f"entry {entry_idx}: missing DOI or abstract. DOI: {doi}, "
                        "abstract: {abstract}"
                    )

        logger.debug(f"Abstracts unpacked: {len(out)}")
        return out
