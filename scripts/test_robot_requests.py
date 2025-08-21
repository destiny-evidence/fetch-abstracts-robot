import json
from pathlib import Path
from uuid import uuid4

from destiny_sdk.references import Reference
from destiny_sdk.robots import RobotRequest
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


def load_request_single_reference() -> dict:
    """
    Load test data for a single reference.

    Returns:
        dict: A dictionary representing the single reference.

    """
    reference_jsonl_file = Path("./contrived_destiny_reference_test.jsonl")
    reference_jsonl = load_data(reference_jsonl_file)

    reference = Reference.from_jsonl(reference_jsonl)

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
        dict: The request object for the enhancement.

    """
    s = session()
    s.headers.update({"Content-type": "application/json", "Accept": "application/json"})
    logger.info(f"Requesting enhancement for single reference at {url}")
    response = s.post(url, json=jsonable_request)
    response.raise_for_status()
    return response


def main() -> None:
    jsonable_request = load_request_single_reference()
    url = "http://localhost:8001/abstract/enhancement/single"
    response = request_enhancement_single_reference(jsonable_request, url)
    logger.success(response)


if __name__ == "__main__":
    main()
