from datetime import datetime
from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.db_models.db import get_db
from app.models.db_models.db_models import CauseOfAction, ComplaintDraft, Fact, FactCauseLink
from app.schemas import (FactCreate, FactExtractRequest, FactExtractResponse, FactGapResponse,
                         FactResponse, LinkCausesRequest, LinkCausesResponse)
from app.services.draft_sync import sync_draft_with_facts
from app.services.fact_extractor import FactExtractor

fact_extractor = FactExtractor()

router = APIRouter(tags=["Facts"])


class AddFactRequest(BaseModel):
    fact_text: str
    related_claims: List[str] = []


def check_affected_drafts(fact_id: int, db: Session):
    """Check and update stale status for drafts using this fact."""
    for draft in db.query(ComplaintDraft).filter(ComplaintDraft.fact_ids.overlap([fact_id])):
        sync_draft_with_facts(draft, db)


# @plugin internal
@router.post("/add", response_model=FactResponse)
@router.post("/", response_model=FactResponse, include_in_schema=False)
def add_fact(request: AddFactRequest, db: Session = Depends(get_db)):
    """Add a new fact with related claims."""
    try:
        new_fact = Fact(
            text=request.fact_text,
            tags=request.related_claims,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(new_fact)
        db.commit()
        db.refresh(new_fact)
        return new_fact
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# @plugin internal
@router.post("/extract", response_model=FactExtractResponse, operation_id="extractFacts")
def extract_facts(request: FactExtractRequest):
    """Extract facts from provided text"""
    facts = fact_extractor.extract_facts(
        text=request.text,
        context=request.context,
        extract_metadata=request.extract_metadata,
        confidence_threshold=request.confidence_threshold,
    )
    return facts


class AuditGapsRequest(BaseModel):
    fact_ids: List[int]


# @plugin internal
@router.post("/audit-gaps", response_model=FactGapResponse, tags=["Facts"])
def analyze_fact_gaps(body: AuditGapsRequest = Body(...), db: Session = Depends(get_db)):
    """Analyze gaps in fact patterns"""
    facts = db.query(Fact).filter(Fact.id.in_(body.fact_ids)).all()
    if not facts:
        raise HTTPException(status_code=404, detail="No facts found")

    gaps = fact_extractor.analyze_gaps(facts)
    return gaps


# @plugin internal
@router.post("/", response_model=FactResponse)
def create_fact(fact: FactCreate, db: Session = Depends(get_db)):
    try:
        incoming = fact.model_dump(exclude_none=True)
        fact_cols = {c.key for c in inspect(Fact).mapper.column_attrs}
        clean = {k: v for k, v in incoming.items() if k in fact_cols}

        record = Fact()
        for k, v in clean.items():
            setattr(record, k, v)
        db.add(record)
        db.commit()
        db.refresh(record)
        return record
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")


# @plugin internal
@router.get("/facts", response_model=list[FactResponse], operation_id="listFacts")
def list_facts(db: Session = Depends(get_db)):
    try:
        return db.query(Fact).all()
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# @plugin internal
@router.get("/{fact_id}", response_model=FactResponse)
def get_fact(fact_id: int, db: Session = Depends(get_db)):
    try:
        record = db.query(Fact).get(fact_id)
        if not record:
            raise HTTPException(status_code=404, detail="Fact not found")
        return record
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# @plugin internal
@router.put("/{fact_id}", response_model=FactResponse)
def update_fact(fact_id: int, fact: FactCreate, db: Session = Depends(get_db)):
    """Update a fact and mark affected drafts as stale."""
    try:
        record = db.query(Fact).get(fact_id)
        if not record:
            raise HTTPException(status_code=404, detail="Fact not found")

        # Update fact
        for key, value in fact.model_dump(exclude_none=True).items():
            setattr(record, key, value)

        db.commit()
        db.refresh(record)

        # Check affected drafts
        check_affected_drafts(fact_id, db)

        return record
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# @plugin internal
@router.delete("/{fact_id}")
def delete_fact(fact_id: int, db: Session = Depends(get_db)):
    try:
        record = db.query(Fact).get(fact_id)
        if not record:
            raise HTTPException(status_code=404, detail="Fact not found")

        # Mark affected drafts as stale before deleting
        check_affected_drafts(fact_id, db)

        db.delete(record)
        db.commit()
        return {"message": f"Fact {fact_id} deleted."}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# @plugin internal
@router.post(
    "/{fact_element_link_id}/causes",
    response_model=LinkCausesResponse,
    operation_id="linkFactToCauses",
)
def link_fact_to_causes(
    fact_element_link_id: int, request: LinkCausesRequest, db: Session = Depends(get_db)
):
    try:
        fact_link = db.query(FactCauseLink).get(fact_element_link_id)
        if not fact_link:
            raise HTTPException(status_code=404, detail="Fact element link not found")

        causes = db.query(CauseOfAction).filter(CauseOfAction.id.in_(request.cause_ids)).all()
        found_cause_ids = [cause.id for cause in causes]
        missing_cause_ids = [cid for cid in request.cause_ids if cid not in found_cause_ids]

        if missing_cause_ids:
            raise HTTPException(
                status_code=404,
                detail=f"Missing causes: {', '.join(map(str, missing_cause_ids))}",
            )

        for cause in causes:
            if cause not in fact_link.causes_of_action:
                fact_link.causes_of_action.append(cause)

        db.commit()
        return LinkCausesResponse(
            status="linked", fact_id=fact_element_link_id, cause_ids=request.cause_ids
        )
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
