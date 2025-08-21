from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile
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
async def upload_file(file: UploadFile):
    """
    Accept a new file upload and save it as 'three_reference_results.jsonl'.

    Args:
        file (UploadFile): The uploaded file.

    Returns:
        dict: A success message.

    """
    try:
        with TARGET_FILE.open("wb") as f:
            f.write(await file.read())
        return {"message": f"File '{TARGET_FILE.name}' successfully uploaded."}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to upload file: {e}"
        ) from e


if __name__ == "__main__":
    # Run the FastAPI app on port 8003
    uvicorn.run(app, host="0.0.0.0", port=8003)  # noqa: S104
