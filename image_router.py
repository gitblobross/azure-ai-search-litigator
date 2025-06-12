import os

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.processor_service import processor

# ✅ Must be named exactly `router` for auto-discovery
router = APIRouter(prefix="/image", tags=["image"])


# @plugin internal
@router.post("/process")
async def process_image(file: UploadFile = File(...)):
    """Process an uploaded image file (JPEG, PNG, HEIC) via OCR."""
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".heic"}:
        raise HTTPException(status_code=400, detail="Unsupported image type.")

    temp_path = f"uploads/temp/{file.filename}"

    contents = await file.read()
    with open(temp_path, "wb") as f:
        f.write(contents)

    result = processor.process_file(temp_path, original_filename=file.filename)

    if result.get("status") == "failed":
        raise HTTPException(status_code=422, detail=result)

    return {
        "status": "success",
        "tags": result.get("tags", []),
        "bucket": result.get("bucket_path"),
        "filename": result.get("filename"),
        "metadata": result.get("metadata", {}),
    }
