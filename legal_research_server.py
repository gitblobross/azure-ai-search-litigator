import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.services.rag_service import RagService

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# RagService uses OpenAIClient internally; ensure API key is set for RAG backends
if not OPENAI_API_KEY:
    # Allow startup but raise on first request if key is missing
    RagService  # noqa: F401

app = FastAPI(title="Litigator Legal Research MCP")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def generate_openapi_yaml():
    """Generate OpenAPI YAML spec file in .well-known directory for GPT integration."""
    try:
        import yaml
    except ImportError:
        return

    schema = app.openapi()
    os.makedirs(".well-known", exist_ok=True)
    path = os.path.join(".well-known", "openapi.yaml")
    with open(path, "w") as f:
        yaml.safe_dump(schema, f, sort_keys=False)


class ResearchRequest(BaseModel):
    query: str
    index: str = "evidence"
    top_k: int = 3


@app.post("/research")
async def research(req: ResearchRequest):
    """Answer legal research questions using RAG-enabled retrieval and GPT."""
    service = RagService()
    try:
        result = await service.query(req.query, index_name=req.index, top_k=req.top_k)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown index {req.index}")
    except Exception as exc:
        detail = str(exc)
        if "corrupt" in detail.lower():
            raise HTTPException(status_code=500, detail="FAISS index file is corrupt")
        raise HTTPException(status_code=500, detail=detail)
    return result


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/.well-known/openapi.yaml")
async def openapi_well_known():
    return FileResponse(os.path.join(".well-known", "openapi.yaml"), media_type="application/yaml")


@app.get("/list_tools")
async def list_tools(request: Request):
    """List available tools for GPT Tools integration."""
    base = str(request.base_url).rstrip("/")
    return [{"name": "research", "method": "POST", "url": f"{base}/research"}]


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8002"))
    uvicorn.run(app, host="0.0.0.0", port=port)
