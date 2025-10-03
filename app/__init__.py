"""Fetch Abstracts Robot Codebase."""
import requests

from app.data_models.generic import (
    APIConfig,
    APIKeyNotPresentError,
    ExternalAPIPriority,
    external_api_priority_batch,
    external_api_priority_single,
)

from app.config import Settings
from app.logger import logger

def prepare_api_config(
    api_configs: list[APIConfig],
    settings: Settings,
    external_api_priority_single: ExternalAPIPriority = external_api_priority_single,
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
            except APIKeyNotPresentError as missing_api_key_error:
                logger.info(f"no API key for {api.name}. not populating config.")
                logger.info(f"original error message: {missing_api_key_error}.")
                continue

    return master_api_config

class Fetcher():
    """Base class for fetchers."""
    
    def __init__(self, master_api_config: dict) -> None:
        self.master_api_config = master_api_config

    def fetch(
        self, url: str, params: dict, headers: dict, *, verbose: bool = False
    ) -> dict:
            """Fetch a response from one of the APIs (generic)."""            
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