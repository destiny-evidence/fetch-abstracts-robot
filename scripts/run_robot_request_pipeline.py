import json
from pathlib import Path
from uuid import uuid4

from destiny_sdk.references import Reference
from destiny_sdk.robots import BatchRobotRequest, RobotRequest
from loguru import logger
from requests import Response, session


def load_data(file_path: Path) -> list[dict] | dict:
    """
    Load JSONL data from a file.

    Args:
        file_path (Path): The path to the JSONL file.

    Returns:
        list[dict] | dict: A list of dictionaries or a single dictionary parsed from the JSONL file.

    """
    with file_path.open("r") as infile:
        loaded_data = [json.loads(line) for line in infile]
    data_to_return = loaded_data if len(loaded_data) > 1 else loaded_data[0]
    return data_to_return


def load_request_single_reference(data_directory: Path) -> dict:
    """
    Load test data for a single reference.

    Args:
        data_directory (Path): The directory containing the reference JSONL file.

    Returns:
        dict: A dictionary representing the single reference.

    """
    reference_jsonl_file = data_directory / "contrived_destiny_reference_test.jsonl"
    reference_jsonl = load_data(reference_jsonl_file)

    reference = Reference.from_jsonl(reference_jsonl)

    request = format_request_object_single_reference(reference)

    rob_req = RobotRequest.model_validate(request)
    logger.info("Formatted single reference request")
    return json.loads(rob_req.model_dump_json())


def generate_batch_reference_request(data_directory: Path) -> dict:
    """
    Load test data for a single reference.

    Args:
        data_directory (Path): The directory containing the reference JSONL file.

    Returns:
        dict: A dictionary representing the single reference.

    """
    file_path = (data_directory / "three_reference_jsonl.jsonl").resolve()
    result_path = (data_directory / "three_reference_results.jsonl").resolve()

    port = 8003
    request = {
        "id": str(uuid4()),
        "reference_storage_url": f"http://localhost:{port}/{file_path.name}",
        "result_storage_url": f"http://localhost:{port}/{result_path.name}",
    }
    robot_request = BatchRobotRequest.model_validate(request)
    logger.info("Formatted batch reference request")
    return json.loads(robot_request.model_dump_json())


def load_request_single_reference_with_crossref_abstract(data_directory: Path) -> dict:
    """
    Load test data for a single reference.

    Args:
        data_directory (Path): The directory containing the reference JSONL file.

    Returns:
        dict: A dictionary representing the single reference.

    """
    reference_json_file = (
        data_directory / "staging_deployment_response_with_abstract_in_crossref.json"
    )
    with reference_json_file.open("r") as infile:
        reference_json = json.load(infile)

    reference = Reference.model_validate(reference_json)

    request = format_request_object_single_reference(reference)

    rob_req = RobotRequest.model_validate(request)
    logger.info("Formatted single reference request")
    return json.loads(rob_req.model_dump_json())


def format_request_object_single_reference(reference: Reference) -> dict:
    """
    Format the request object for the robot.

    Args:
        reference (Reference): The reference object to include in the request.

    Returns:
        dict: The formatted request object.

    """
    return {
        "id": str(uuid4()),
        "reference": reference,
    }


def request_enhancement_single_reference(jsonable_request: dict, url: str) -> Response:
    """
    Create a request for enhancing a single reference.

    Args:
        jsonable_request (dict): The JSON-serializable request object.
        url (str): The URL for the enhancement request.

    Returns:
        Response: The response object from the enhancement request.

    """
    s = session()
    s.headers.update({"Content-type": "application/json", "Accept": "application/json"})
    logger.info(f"Requesting enhancement for single reference at {url}")
    response = s.post(url, json=jsonable_request)
    response.raise_for_status()
    return response


def request_enhancement_batch_references(jsonable_request: dict, url: str) -> Response:
    """
    Create a request for enhancing a batch of references.

    Args:
        jsonable_request (dict): The JSON-serializable request object.
        url (str): The URL for the enhancement request.

    Returns:
        Response: The response object from the enhancement request.

    """
    s = session()
    s.headers.update({"Content-type": "application/json", "Accept": "application/json"})
    logger.info(f"Requesting enhancement for batch references at {url}")
    response = s.post(url, json=jsonable_request)
    response.raise_for_status()
    return response


def run_single_reference_enhancement(data_directory: Path) -> None:
    """
    Run enhancement for a single reference.

    Args:
        data_directory (Path): The directory containing the reference JSONL file.

    """
    jsonable_request = load_request_single_reference_with_crossref_abstract(
        data_directory
    )
    url = "http://localhost:8001/abstract/enhancement/single"
    response = request_enhancement_single_reference(jsonable_request, url)
    logger.success(response)


def run_batch_reference_enhancement(data_directory: Path) -> None:
    """
    Run enhancement for a batch of references.

    Args:
        data_directory (Path): The directory containing the reference JSONL file.

    """
    jsonable_request = generate_batch_reference_request(data_directory)
    url = "http://localhost:8001/abstract/enhancement/batch"
    response = request_enhancement_batch_references(jsonable_request, url)
    logger.success(response)


def main() -> None:
    """Run the main pipeline for reference enhancement."""
    data_directory = Path(__file__).parent.resolve() / "test_data"
    data_directory.mkdir(exist_ok=True)
    run_batch_reference_enhancement(data_directory)


if __name__ == "__main__":
    main()
