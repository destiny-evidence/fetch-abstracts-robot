"""Define the main function to run the local abstract fetcher robot."""

import json
import os
import sys
from pathlib import Path

from cyclopts import App
from destiny_sdk.robots import LinkedRobotError
from loguru import logger

from far.config import Environment, get_settings
from far.data_models.generic import ExternalAPI
from far.enhancement_processor import BatchEnhancementGenerationError
from far.local.config import set_up_processor
from far.local.utils import get_destiny_references
from far.logger import set_up_logger
from far.utils import get_version_number

os.environ["ENV"] = Environment.LOCAL
os.environ["DESTINY_REPOSITORY_URL"] = "https://example.com"

app = App(
    name="fetch-abstracts",
    version=get_version_number(),
)


@app.default
def main(
    doi_list: Path,
    output_directory: Path = Path(__file__).parent.parent.parent / "output",
    exclude_api: list[ExternalAPI] | None = None,
) -> None:
    """
    Run the local abstract retrieval workflow.

    Args:
        doi_list (Path): Path to a file containing a list of DOIs to process.
        output_directory (Path, optional):
            Path to the directory where the output will be saved.
            Defaults to the "output" directory in the project root.
        exclude_api (list[ExternalAPI] | None, optional):
            A list of APIs to exclude from the processing.
            Defaults to None.

    """
    set_up_logger()
    settings = get_settings()
    processor = set_up_processor(settings, exclude_api)
    output_directory.mkdir(parents=True, exist_ok=True)
    output_file = output_directory / f"abstracts_{doi_list.stem}.json"

    references = get_destiny_references(doi_list)

    try:
        enhancements = processor.create_abstract_enhancement(
            references=references,
        )
    except BatchEnhancementGenerationError as no_abstracts_found_error:
        error_message = (
            f"Error during abstract enhancement generation: {no_abstracts_found_error}"
        )
        logger.critical(error_message)
        with output_file.open("w") as file:
            json_output = {
                "abstracts": None,
                "dois_with_abstracts": None,
                "dois_without_abstracts": [
                    reference.identifiers[0].identifier for reference in references
                ],
            }
            file.write(json.dumps(json_output, indent=2))
        sys.exit(1)

    abstract_ids = []
    for enhancement in enhancements:
        has_valid_abstract_enhancement = (
            not isinstance(enhancement, LinkedRobotError)
            and enhancement.content
            and enhancement.content.abstract
        )
        if has_valid_abstract_enhancement:
            reference_doi = next(
                reference.identifiers[0].identifier
                for reference in references
                if reference.id == enhancement.reference_id
            )

            abstract_ids.append(
                {
                    "far_reference_id": str(enhancement.reference_id),
                    "abstract": enhancement.content.abstract,
                    "doi": reference_doi,
                }
            )

    dois_with_abstracts = []
    dois_without_abstracts = []
    reference_ids_with_abstracts = {
        abstract_id.get("far_reference_id") for abstract_id in abstract_ids
    }
    for reference in references:
        if str(reference.id) in reference_ids_with_abstracts:
            dois_with_abstracts.append(reference.identifiers[0].identifier)
        else:
            dois_without_abstracts.append(reference.identifiers[0].identifier)

    abstract_dois = [
        {k: v for k, v in d.items() if k != "far_reference_id"} for d in abstract_ids
    ]

    logger.info(f"DOIs with abstracts: {dois_with_abstracts}")
    logger.info(f"DOIs without abstracts: {dois_without_abstracts}")

    with output_file.open("w") as file:
        json_output = {
            "abstracts": abstract_dois,
            "dois_with_abstracts": dois_with_abstracts,
            "dois_without_abstracts": dois_without_abstracts,
        }
        file.write(json.dumps(json_output, indent=2))


if __name__ == "__main__":
    app()
