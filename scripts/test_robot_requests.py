import json
from pathlib import Path
from uuid import uuid4

from destiny_sdk.robots import BatchRobotRequest
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


def generate_batch_reference_request() -> dict:
    """
    Load test data for a batch of references.

    Returns:
        dict: A dictionary representing the batch of references.

    """
    file_path = Path("./three_reference_jsonl.jsonl").resolve()
    result_path = Path("./three_reference_results.jsonl").resolve()

    port = 8003
    request = {
        "id": str(uuid4()),
        "reference_storage_url": f"http://localhost:{port}/{file_path.name}",
        "result_storage_url": f"http://localhost:{port}/{result_path.name}",
    }
    robot_request = BatchRobotRequest.model_validate(request)
    logger.info("Formatted batch reference request")
    return json.loads(robot_request.model_dump_json())


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


def run_batch_reference_enhancement() -> None:
    jsonable_request = generate_batch_reference_request()
    url = "http://localhost:8001/abstract/enhancement/batch"
    response = request_enhancement_batch_references(jsonable_request, url)
    logger.success(response)


def main() -> None:
    run_batch_reference_enhancement()


if __name__ == "__main__":
    main()
