import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

app = FastAPI(title="Litigator Legal NLP")
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


class SummarizeRequest(BaseModel):
    text: str


@app.post("/summarize", operation_id="summarize_post")
async def summarize(req: SummarizeRequest):
    """Summarize legal text using GPT-4."""
    if not openai_client:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set")
    prompt = f"Summarize the following legal text:\n{req.text}"
    try:
        resp = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a legal NLP assistant summarizing documents.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=1000,
            temperature=0.3,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"OpenAI error: {exc}") from exc
    return {"summary": resp.choices[0].message.content}


@app.post("/summarize_post")
async def summarize_post(req: SummarizeRequest):
    """Alias for /summarize endpoint."""
    return await summarize(req)


@app.get("/health", operation_id="health_get")
async def health():
    return {"ok": True}


@app.get("/.well-known/openapi.yaml")
async def openapi_well_known():
    return FileResponse(os.path.join(".well-known", "openapi.yaml"), media_type="application/yaml")


@app.get("/list_tools")
async def list_tools(request: Request):
    """List available tools for GPT Tools integration."""
    base = str(request.base_url).rstrip("/")
    return [{"name": "summarize", "method": "POST", "url": f"{base}/summarize"}]


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8002"))
    uvicorn.run(app, host="0.0.0.0", port=port)
