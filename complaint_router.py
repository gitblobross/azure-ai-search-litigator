from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.db_models.db import get_db
from app.models.db_models.db_models import ComplaintSection
from app.routers.discovery import plugin_router
from app.schemas.complaint_schemas import ComplaintSectionCreate, ComplaintSectionResponse



router = APIRouter(prefix="/complaints", tags=["Complaints"])
plugin_router("complaint")(router)


@router.post(
    "/",
    response_model=ComplaintSectionResponse,
    status_code=201,
)
def create_section(
    section: ComplaintSectionCreate,
    db: Session = Depends(get_db),
):
    if not section.section:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="`section` field is required",
        )

    existing = db.query(ComplaintSection).filter_by(section=section.section).first()
    if existing:
        raise HTTPException(status_code=409, detail="Section already exists")

    record = ComplaintSection(
        section=section.section,
        content=section.content,
    )

    db.add(record)
    db.commit()

    db.refresh(record, attribute_names=["facts", "exhibits"])
    return record
