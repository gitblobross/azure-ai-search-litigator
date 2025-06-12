from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models.db_models import CauseOfAction, FactElementLink, LegalElement
from app.models.db_models.db import get_db

router = APIRouter()


# @plugin internal
@router.get("/matrix/generate", tags=["Matrix"], summary="Generate Claim Matrix")
def generate_claim_matrix(db: Session = Depends(get_db)):
    causes = db.query(CauseOfAction).all()

    matrix = []
    for cause in causes:
        elements = db.query(LegalElement).filter(LegalElement.cause_id == cause.id).all()

        matrix_entry = {"cause": cause.name, "cause_id": cause.id, "elements": []}

        for element in elements:
            fact_links = (
                db.query(FactElementLink).filter(FactElementLink.element_id == element.id).all()
            )

            facts = []
            for link in fact_links:
                fact = link.fact
                if fact:
                    facts.append(
                        {
                            "fact_id": fact.id,
                            "text": fact.text,
                            "date": fact.date,
                            "source": fact.source,
                            "tags": fact.tags,
                            "exhibits": [e.filename for e in fact.exhibits],
                            "note": link.note,
                            "confidence": link.confidence,
                        }
                    )

            matrix_entry["elements"].append(
                {"element": element.name, "element_id": element.id, "facts": facts}
            )

        matrix.append(matrix_entry)

    return {"claims": matrix}
