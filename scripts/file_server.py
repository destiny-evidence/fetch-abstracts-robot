from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

app = FastAPI()

BASE_DIR = Path(__file__).parent.resolve()
TARGET_FILE = BASE_DIR / "three_reference_jsonl.jsonl"


@app.get("/three_reference_jsonl.jsonl")
async def serve_file():
    """
    Serve the specific file 'three_reference_jsonl.jsonl'.

    Returns:
        FileResponse: The file response for the requested file.

    """
    if not TARGET_FILE.exists() or not TARGET_FILE.is_file():
        return {"error": f"File '{TARGET_FILE.name}' not found."}
    return FileResponse(TARGET_FILE)


@app.put("/three_reference_results.jsonl")
async def upload_file(data: bytes):
    """
    Accept a new file upload as UTF-8 encoded bytes and save it as 'three_reference_results.jsonl'.

    Args:
        data (bytes): The UTF-8 encoded bytes of the uploaded file.

    Returns:
        dict: A success message.

    """
    target_file = BASE_DIR / "three_reference_results.jsonl"
    try:
        content = data.decode("utf-8")
        with target_file.open("w", encoding="utf-8") as f:
            f.write(content)
        return {"message": f"File '{target_file.name}' successfully uploaded."}
    except UnicodeDecodeError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid UTF-8 encoding: {e}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to upload file: {e}"
        ) from e


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)  # noqa: S104
