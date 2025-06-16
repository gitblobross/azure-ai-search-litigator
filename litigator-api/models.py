from pydantic import BaseModel

class DocumentData(BaseModel):
    id: str
    blob_url: str

class Claim(BaseModel):
    id: str
    title: str
    description: str = None

class ChatRequest(BaseModel):
    question: str