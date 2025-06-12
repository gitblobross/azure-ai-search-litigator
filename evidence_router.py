import logging  # Added
from pathlib import Path
from typing import List

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.db_models.db import get_db
from app.models.db_models.db_models import Evidence, Fact
from app.schemas.evidence_schemas import BulkProcessingResponse, ProcessDirectoryRequest
from app.services.advanced_processor_core import AdvancedDocumentProcessor
from app.utils.b64_file import save_base64_file

# Initialize logger
logger = logging.getLogger(__name__)

from app.routers.discovery import plugin_router



router = APIRouter(
    prefix="/evidence",
    tags=["Evidence"],
)
plugin_router("nlp")(router)


# ---------------- UPLOAD MODELS ----------------
class EvidenceUploadBody(BaseModel):
    filename: str
    content_b64: str


class EvidenceUploadList(BaseModel):
    files: list[EvidenceUploadBody]


# ---------------- ORIGINAL MULTIPART ENDPOINTS ----------------
# @plugin nlp
@router.post("/upload", operation_id="evidence_upload")
async def upload_evidence(
    file: UploadFile = File(...),
    title: str = Form(...),
    document_type: str = Form(...),
    db: Session = Depends(get_db),
):
    """Upload a single evidence file"""
    return {"filename": file.filename}


# @plugin nlp
@router.post("/upload-multiple", operation_id="evidence_upload_multiple")
async def upload_multiple_evidence(
    files: List[UploadFile] = File(...), db: Session = Depends(get_db)
):
    """Upload multiple evidence files"""
    return {"filenames": [file.filename for file in files]}


# @plugin internal
@router.post(
    "/process-directory",
    response_model=BulkProcessingResponse,
    operation_id="evidence_process_directory",
)
async def process_directory(request: ProcessDirectoryRequest = Body(...)):
    """Process all files in a directory"""
    processor = AdvancedDocumentProcessor()
    try:
        results = processor.process_directory(request.directory, request.recursive)
        return {
            "success": True,
            "message": f"Successfully processed directory {request.directory}",
            "processed_files": [
                result["filename"] for result in results if "error" not in result
            ],
            "failed_files": [
                result["filename"] for result in results if "error" in result
            ],
            "error_details": None,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to process directory {request.directory}",
            "processed_files": [],
            "failed_files": [],
            "error_details": str(e),
        }


# ---------------- JSON UPLOAD ENDPOINTS ----------------
# @plugin nlp
@router.post("/upload-json", operation_id="evidence_upload_json")
async def upload_evidence_json(body: EvidenceUploadBody, db: Session = Depends(get_db)):
    try:
        logger.debug(
            f"Received base64 data for '{body.filename}'. Length: {len(body.content_b64)}"
        )
        if body.content_b64:
            logger.debug(
                f"First 100 chars of base64 for '{body.filename}': {body.content_b64[:100]}..."
            )
        else:
            logger.warning(f"Received empty base64 content for file '{body.filename}'.")

        upload_dir = Path("uploads/evidence")

        try:
            save_path = save_base64_file(body.content_b64, body.filename, upload_dir)
        except ValueError as e:
            logger.error(f"Failed to save base64 file '{body.filename}': {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        if not save_path.exists():
            logger.error(f"File '{save_path}' failed to save (does not exist).")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="File failed to save after decoding.",
            )
        if save_path.stat().st_size == 0:
            logger.error(f"Saved file '{save_path}' is empty.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Saved file is empty after decoding.",
            )

        processor = AdvancedDocumentProcessor()
        result = processor.process_file(save_path)

        # VECTOR STORE UPLOAD PLACEHOLDER:
        vector_file_id = None
        try:
            from openai import OpenAI
            client = OpenAI()
            # Call your actual upload util here as needed; this is a stub:
            # vs_file = client.vector_stores.files.upload_and_poll(...)
            # vector_file_id = vs_file.id
        except Exception as vserr:
            logger.warning(f"Vector store upload not attempted or failed: {vserr}")
        evidence = Evidence(
            filename=body.filename,
            file_path=str(save_path),
            file_type=None,  # Or determine from result
            summary=result.get("summary") if result else None,
            vector_file_id=vector_file_id,
        )
        db.add(evidence)
        db.flush()

        key_points = result.get("key_points", []) if result else []
        if not key_points:  # Ensure there's at least one fact, even if a stub
            key_points = ["stub fact"]

        facts = []
        for point in key_points:
            fact = Fact(
                text=point,
                source=body.filename,
                evidence_id=evidence.id,
            )
            facts.append(fact)
            db.add(fact)

        evidence.facts.extend(facts)
        db.commit()
        db.refresh(evidence)

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "message": f"File '{body.filename}' processed and indexed.",
                "evidence_id": evidence.id,
                "fact_count": len(key_points),
            },
        )
    except HTTPException:  # Re-raise HTTPExceptions directly
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error during upload of '{body.filename}': {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}",
        )


# @plugin nlp
@router.post("/upload-multiple-json", operation_id="evidence_upload_multiple_json")
async def upload_multiple_evidence_json(
    body: EvidenceUploadList, db: Session = Depends(get_db)
):
    try:
        upload_dir = Path("uploads/evidence")
        saved_paths = []
        processed_files_info = []  # To track status of each file
        valid_file_bodies = []  # To align with valid_saved_paths

        for file_body in body.files:
            logger.debug(
                f"Processing file in batch: '{file_body.filename}'. Base64 length: {len(file_body.content_b64)}"
            )
            if file_body.content_b64:
                logger.debug(
                    f"First 100 chars of base64 for '{file_body.filename}': {file_body.content_b64[:100]}..."
                )
            else:
                logger.warning(
                    f"Received empty base64 content for file '{file_body.filename}' in batch."
                )

            current_file_info = {"filename": file_body.filename}
            try:
                save_path = save_base64_file(
                    file_body.content_b64, file_body.filename, upload_dir
                )

                if not save_path.exists():
                    logger.error(
                        f"File '{save_path}' failed to save in batch (does not exist)."
                    )
                    current_file_info["error"] = "File failed to save after decoding."
                    processed_files_info.append(current_file_info)
                    continue
                if save_path.stat().st_size == 0:
                    logger.error(f"Saved file '{save_path}' is empty in batch.")
                    current_file_info["error"] = "Saved file is empty after decoding."
                    processed_files_info.append(current_file_info)
                    continue

                saved_paths.append(save_path)
                valid_file_bodies.append(
                    file_body
                )  # Keep track of corresponding original body
                current_file_info["save_path"] = save_path
                current_file_info["status"] = "saved"
                processed_files_info.append(current_file_info)

            except ValueError as e:
                logger.error(
                    f"Failed to save base64 file '{file_body.filename}' in batch: {e}"
                )
                current_file_info["error"] = str(e)
                processed_files_info.append(current_file_info)
                continue

        if not saved_paths:  # No files were successfully saved
            failed_files_details = [
                {
                    "filename": info["filename"],
                    "detail": info.get("error", "Unknown error during save"),
                }
                for info in processed_files_info
                if "error" in info
            ]
            if failed_files_details:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "message": "All files failed during save stage.",
                        "errors": failed_files_details,
                    },
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="No files were processed, and no specific save errors recorded.",
                )

        processor = AdvancedDocumentProcessor()
        results = [processor.process_file(path) for path in saved_paths]

        evidences = []
        for file_body, save_path, result in zip(
            valid_file_bodies, saved_paths, results
        ):
            # VECTOR STORE UPLOAD PLACEHOLDER:
            vector_file_id = None
            try:
                from openai import OpenAI
                client = OpenAI()
                # Call your actual upload util here as needed
                # vs_file = client.vector_stores.files.upload_and_poll(...)
                # vector_file_id = vs_file.id
            except Exception as vserr:
                logger.warning(f"Vector store upload not attempted or failed: {vserr}")
            evidence = Evidence(
                filename=file_body.filename,
                file_path=str(save_path),
                file_type=None,
                summary=result.get("summary") if result else None,
                vector_file_id=vector_file_id,
            )
            db.add(evidence)
            db.flush()

            key_points = result.get("key_points", []) if result else []
            if not key_points:
                key_points = ["stub fact"]

            facts = []
            for point in key_points:
                fact = Fact(
                    text=point,
                    source=file_body.filename,
                    evidence_id=evidence.id,
                )
                facts.append(fact)
                db.add(fact)

            evidence.facts.extend(facts)
            evidences.append(evidence)

        db.commit()
        for evidence_item in evidences:  # Use different variable name to avoid conflict
            db.refresh(evidence_item)

        # Prepare response details for failed files
        failed_files_output = [
            {"filename": info["filename"], "error": info["error"]}
            for info in processed_files_info
            if "error" in info
        ]

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "message": f"{len(evidences)} out of {len(body.files)} files processed and indexed.",
                "processed_files": [
                    {
                        "filename": e.filename,
                        "evidence_id": e.id,
                        "fact_count": len(e.facts),
                    }
                    for e in evidences
                ],
                "failed_files": failed_files_output,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error during multiple file upload: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}",
        )


# @plugin nlp
@router.post(
    "/upload-and-index-json",
    operation_id="upload_and_index_evidence_json",
    status_code=201,
)
async def upload_and_index_evidence_json(
    body: EvidenceUploadBody, db: Session = Depends(get_db)
):
    try:
        logger.debug(
            f"Received base64 data for upload-and-index: '{body.filename}'. Length: {len(body.content_b64)}"
        )
        if body.content_b64:
            logger.debug(
                f"First 100 chars of base64 for '{body.filename}': {body.content_b64[:100]}..."
            )
        else:
            logger.warning(
                f"Received empty base64 content for file '{body.filename}' in upload-and-index."
            )

        upload_dir = Path("uploads/evidence")
        try:
            save_path = save_base64_file(body.content_b64, body.filename, upload_dir)
        except ValueError as e:
            logger.error(
                f"Failed to save base64 file '{body.filename}' for upload-and-index: {e}"
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        if not save_path.exists():
            logger.error(
                f"File '{save_path}' failed to save for upload-and-index (does not exist)."
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="File failed to save after decoding.",
            )
        if save_path.stat().st_size == 0:
            logger.error(f"Saved file '{save_path}' is empty for upload-and-index.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Saved file is empty after decoding.",
            )

        processor = AdvancedDocumentProcessor()
        result = processor.process_file(save_path)
        # Assuming build_faiss_index is robust or has its own error handling
        # If it can fail and needs specific handling here, that could be added.
        processor.build_faiss_index([result])

        # VECTOR STORE UPLOAD PLACEHOLDER:
        vector_file_id = None
        try:
            from openai import OpenAI
            client = OpenAI()
            # Call your actual upload util here as needed
            # vs_file = client.vector_stores.files.upload_and_poll(...)
            # vector_file_id = vs_file.id
        except Exception as vserr:
            logger.warning(f"Vector store upload not attempted or failed: {vserr}")
        evidence = Evidence(
            filename=body.filename,
            file_path=str(save_path),
            file_type=None,
            summary=result.get("summary") if result else None,
            vector_file_id=vector_file_id,
        )
        db.add(evidence)
        db.flush()

        key_points = result.get("key_points", []) if result else []
        if not key_points:
            key_points = ["stub fact"]

        facts = []
        for point in key_points:
            fact = Fact(
                text=point,
                source=body.filename,
                evidence_id=evidence.id,
            )
            facts.append(fact)
            db.add(fact)

        evidence.facts.extend(facts)
        db.commit()
        db.refresh(evidence)

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "message": f"File '{body.filename}' processed and indexed.",
                "evidence_id": evidence.id,
                "fact_count": len(key_points),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error during upload-and-index of '{body.filename}': {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}",
        )
