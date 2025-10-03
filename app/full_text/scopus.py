"""Retrieve full text from Scopus."""

from app.config import get_settings, Settings

from app import Fetcher, prepare_api_config
from app.data_models.scopus import scopus_fulltext_api_config
from loguru import logger

class ScopusFullTextFetcher(Fetcher):
    """Fetch full text from Scopus."""

    def __init__(self, master_api_config: dict, timeout: int = 60) -> None:
        """
        Initialize the ScopusFullTextFetcher.

        Args:
            master_api_config (dict, optional): Configuration for the API. Defaults to None.
            timeout (int, optional): Network timeout. Defaults to 60.

        """
        super().__init__(master_api_config=master_api_config)
        self.master_api_config = master_api_config  # type: dict
        self.timeout = timeout


def main():
    """Main function to demonstrate fetching full text from Scopus."""
    settings: Settings = get_settings()
    api_config = prepare_api_config(
        api_configs=[scopus_fulltext_api_config],
        settings=settings,
        external_api_priority_single=None,
        external_api_priority_batch=None,
    )
    fetcher = ScopusFullTextFetcher(
        master_api_config={"scopus_fulltext": api_config}, timeout=60
    )
    doi = ["10.1016/j.jiph.2024.102615"]
    query_result = api_config.populate_query(query=doi)

    url = query_result.get("url", "")
    params = query_result.get("query_params", {})
    headers = query_result.get("headers", {})

    response = fetcher.fetch(url=url, params=params, headers=headers, verbose=True)
    logger.info(response)

if __name__ == "__main__":
    main()