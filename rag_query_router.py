import logging
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.routers.discovery import plugin_router
from app.services.rag_service import RagService



router = APIRouter(prefix="/chat", tags=["RAG"])
plugin_router("nlp")(router)
rag = RagService()
logger = logging.getLogger(__name__)


class RagRequest(BaseModel):
    query: str
    index: str = "evidence"
    top_k: int = 3


# @plugin nlp
@router.post("/rag", operation_id="chat_rag")
async def rag_endpoint(req: RagRequest):
    """Query RAG system with a question, returning answer and sources."""
    try:
        start_time = time.time()
        result = await rag.query(req.query, index_name=req.index, top_k=req.top_k)
        duration_ms = (time.time() - start_time) * 1000
        logger.info(f"RAG answered in {duration_ms:.2f} ms")
        return result
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown index {req.index}")
    except Exception as e:
        if "corrupt" in str(e).lower():
            raise HTTPException(status_code=500, detail="FAISS index file is corrupt")
        raise HTTPException(status_code=500, detail=str(e))
