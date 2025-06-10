import json
import os
from typing import Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from openai import OpenAI  # only used after key check
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.db_models.db import get_db
from app.models.db_models.db_models import ConversationMessage, Fact

router = APIRouter(prefix="/chat", tags=["Chat"])


# ---------- helpers ---------------------------------------------------------

from app.settings import Settings


def require_api_key() -> str:
    settings = Settings()
    key = settings.openai_api_key
    if not key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    return key


def gpt_client() -> OpenAI:
    return OpenAI(api_key=require_api_key())


# ---------- pydantic models -------------------------------------------------
class ChatRequest(BaseModel):
    session_id: str
    user_message: str


class ChatResponse(BaseModel):
    assistant_response: str
    conversation_history: List[dict]


class DiscoveryRequest(BaseModel):
    facts: List[str]
    claims: List[str]


class DiscoveryResponse(BaseModel):
    interrogatories: List[str]
    document_requests: List[str]


class MotionResponseRequest(BaseModel):
    facts: List[str]
    claims: List[str]
    motion_type: Optional[str] = "Motion to Dismiss"


class MotionResponseResponse(BaseModel):
    draft: str


class SettlementRequest(BaseModel):
    facts: List[str]
    claims: List[str]
    terms: Optional[str] = None


class SettlementResponse(BaseModel):
    draft: str


class DepositionQARequest(BaseModel):
    witness: str
    perspective: Optional[str] = None


class DepositionQAResponse(BaseModel):
    questions: List[str]


class TimelineResponse(BaseModel):
    timeline: List[Dict[str, str]]
    narrative: str


# ---------- chat endpoint ---------------------------------------------------
# @plugin internal
@router.post("/", response_model=ChatResponse, operation_id="chat_session")
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    client = gpt_client()

    history = (
        db.query(ConversationMessage)
        .filter_by(session_id=request.session_id)
        .order_by(ConversationMessage.timestamp)
        .all()
    )

    messages = [{"role": m.role, "content": m.content} for m in history]
    messages.append({"role": "user", "content": request.user_message})

    resp = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        temperature=0.3,
        max_tokens=1000,
    )
    assistant = resp.choices[0].message.content

    db.add_all(
        [
            ConversationMessage(
                session_id=request.session_id, role="user", content=request.user_message
            ),
            ConversationMessage(session_id=request.session_id, role="assistant", content=assistant),
        ]
    )
    db.commit()

    new_history = [
        {"role": m.role, "content": m.content, "timestamp": m.timestamp.isoformat()}
        for m in db.query(ConversationMessage)
        .filter_by(session_id=request.session_id)
        .order_by(ConversationMessage.timestamp)
    ]
    return ChatResponse(assistant_response=assistant, conversation_history=new_history)


# @plugin internal
@router.get(
    "/history/{session_id}",
    response_model=ChatResponse,
    operation_id="chat_history",
    summary="Session History",
)
def chat_history(session_id: str, db: Session = Depends(get_db)):
    """Return prior messages for a chat session."""
    history = (
        db.query(ConversationMessage)
        .filter_by(session_id=session_id)
        .order_by(ConversationMessage.timestamp)
        .all()
    )

    formatted = [
        {
            "role": m.role,
            "content": m.content,
            "timestamp": m.timestamp.isoformat(),
        }
        for m in history
    ]

    last_assistant = next((m.content for m in reversed(history) if m.role == "assistant"), "")

    return ChatResponse(
        assistant_response=last_assistant,
        conversation_history=formatted,
    )


# ---------- discovery helper -----------------------------------------------
# @plugin internal
@router.post(
    "/discovery_helper",
    response_model=DiscoveryResponse,
    operation_id="chat_discovery_helper",
)
def discovery_helper(req: DiscoveryRequest):
    client = gpt_client()
    prompt = (
        f"Draft interrogatories and document requests for facts {req.facts} "
        f"and claims {req.claims}. Return JSON with keys "
        "'interrogatories' and 'document_requests'."
    )
    resp = (
        client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You draft discovery."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        .choices[0]
        .message.content.strip()
    )

    try:
        parsed = json.loads(resp)
        return DiscoveryResponse(**parsed)
    except json.JSONDecodeError:
        lines = [line.strip() for line in resp.splitlines() if line.strip()]
        inter = [line for line in lines if line.lower().startswith("interrogatory")]
        rfp = [line for line in lines if line.lower().startswith("request")]
        return DiscoveryResponse(interrogatories=inter, document_requests=rfp)


# ---------- motion response -------------------------------------------------
# @plugin internal
@router.post(
    "/draft_motion_response",
    response_model=MotionResponseResponse,
    operation_id="chat_draft_motion",
)
def draft_motion(req: MotionResponseRequest):
    client = gpt_client()
    cap = os.getenv("CAP_API_BASE", "http://cap-web:8000")
    query = " OR ".join(req.claims or req.facts)
    try:
        cases = httpx.get(f"{cap}/search", params={"q": query}).json().get("results", [])[:5]
    except Exception:
        cases = []
    cases_txt = "\n".join(f"- {c['title']} ({c['id']})" for c in cases) or "No cases found."
    prompt = (
        f"Facts: {req.facts}\nClaims: {req.claims}\nCases:\n{cases_txt}\n\n"
        f"Draft an opposition to the {req.motion_type} (IRAC format, cite cases)."
    )
    draft = (
        client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You write briefs."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=1200,
        )
        .choices[0]
        .message.content.strip()
    )
    return MotionResponseResponse(draft=draft)


# ---------- settlement demand ----------------------------------------------
# @plugin internal
@router.post(
    "/draft_settlement_demand",
    response_model=SettlementResponse,
    operation_id="chat_draft_settlement",
)
def settlement(req: SettlementRequest):
    client = gpt_client()
    prompt = (
        f"Facts: {req.facts}\nClaims: {req.claims}\nTerms: {req.terms or 'Open'}\n\n"
        "Draft a persuasive settlement demand letter."
    )
    draft = (
        client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You write settlement letters."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=800,
        )
        .choices[0]
        .message.content.strip()
    )
    return SettlementResponse(draft=draft)


# ---------- deposition Q&A --------------------------------------------------
# @plugin internal
@router.post(
    "/deposition_questions",
    response_model=DepositionQAResponse,
    operation_id="chat_deposition_qa",
)
def deposition_qs(req: DepositionQARequest):
    client = gpt_client()
    prompt = f"Suggest deposition questions for {req.witness} ({req.perspective or 'general'} perspective)."
    qs = (
        client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You draft depo questions."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        .choices[0]
        .message.content.strip()
        .splitlines()
    )
    return DepositionQAResponse(questions=[q.strip() for q in qs if q.strip()])


# ---------- timeline narrative ---------------------------------------------
# @plugin internal
@router.get("/case_timeline", response_model=TimelineResponse, operation_id="chat_timeline")
def timeline(db: Session = Depends(get_db)):
    client = gpt_client()
    facts = db.query(Fact).order_by(Fact.created_at).all()
    tl = [{"date": f.date or f.created_at.isoformat(), "text": f.text} for f in facts]
    events = "\n".join(f"{t['date']}: {t['text']}" for t in tl)
    narrative = (
        client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You summarise facts."},
                {"role": "user", "content": f"Provide a concise narrative:\n{events}"},
            ],
            temperature=0.3,
            max_tokens=600,
        )
        .choices[0]
        .message.content.strip()
    )
    return TimelineResponse(timeline=tl, narrative=narrative)
