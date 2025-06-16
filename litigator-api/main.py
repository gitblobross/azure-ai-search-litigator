from fastapi import FastAPI, UploadFile, File, HTTPException
from models import ChatRequest, Claim, DocumentData
from services import ocr_document, search_claims, openai_chat, upload_blob, save_claim
from settings import settings

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello from Litigator-FastAPI"}

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    contents = await file.read()
    try:
        url = upload_blob(contents, file.filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"url": url}

@app.post("/ocr")
async def ocr(file: UploadFile = File(...)):
    contents = await file.read()
    try:
        result = ocr_document(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return result

@app.get("/search")
async def search(q: str):
    try:
        results = search_claims(q)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return results

@app.post("/chat")
async def chat(chat_request: ChatRequest):
    try:
        response = openai_chat(chat_request.question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return response

@app.post("/claims")
async def create_claim(claim: Claim):
    try:
        save_claim(claim.dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "saved"}