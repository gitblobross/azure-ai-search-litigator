# app/routers/legal_elements_router.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.db_models.db import get_db
from app.routers.discovery import plugin_router
from app.schemas import (CompareFactsRequest, CompareFactsResponse, LegalElementBase,
                         LegalElementResponse, LegalElementsCompareRequest,
                         LegalElementsCompareResponse, LegalElementsResponse)
from app.services.legal_elements import LegalElementsService



router = APIRouter(prefix="/legal-elements", tags=["Legal Elements"])
plugin_router("research")(router)

# Singleton service instance
service = LegalElementsService()


# @plugin research
@router.post("/", response_model=LegalElementResponse)
def create_legal_element(
    payload: LegalElementBase,
    db: Session = Depends(get_db),
):
    """
    Create a new legal element in the database.
    """
    el = service.create(db, payload)
    return el


# @plugin research
@router.get("/", response_model=LegalElementsResponse)
def list_legal_elements(db: Session = Depends(get_db)):
    """
    List all legal elements, grouped by cause/category.
    """
    data = service.list_all(db)  # returns Dict[str, List[LegalElementResponse]]
    return LegalElementsResponse(legalElements=data)


# @plugin research
@router.get("/{element_id}", response_model=LegalElementResponse)
def get_legal_element(
    element_id: int,
    db: Session = Depends(get_db),
):
    """
    Fetch a single legal element by its ID.
    """
    el = service.get_by_id(db, element_id)
    if not el:
        raise HTTPException(status_code=404, detail="Legal element not found")
    return el


# @plugin research
@router.post("/compare-facts", response_model=CompareFactsResponse)
def compare_facts_to_elements(
    req: CompareFactsRequest,
    db: Session = Depends(get_db),
):
    """
    Given a list of facts, return matching cause/element pairs.
    """
    matches = service.compare_facts(db, req.facts)
    return CompareFactsResponse(matches=matches)


# @plugin research
@router.post("/compare-elements", response_model=LegalElementsCompareResponse)
def compare_legal_elements(
    req: LegalElementsCompareRequest,
    db: Session = Depends(get_db),
):
    """
    Compare multiple legal elements for similarity/conflict/coverage.
    """
    comparison = service.compare_elements(
        db,
        element_ids=req.element_ids,
        comparison_type=req.comparison_type,
        context=req.context,
        include_facts=req.include_facts,
        threshold=req.threshold,
    )
    return comparison
