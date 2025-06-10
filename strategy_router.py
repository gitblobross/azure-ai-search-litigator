"""
Strategy Advisor API endpoints for the Legal Document Analysis API.
These endpoints provide legal strategy suggestions based on case facts.
"""

import logging
import os
from typing import List

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.db_models.db import get_db
from app.models.db_models.db_models import CauseOfAction, Fact
from app.schemas import (AnalyzeCasePhaseRequest, AnalyzeCasePhaseResponse, StrategyRequest,
                         StrategyResponse)
from app.services.strategy_advisor import StrategyAdvisor

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

from app.routers.discovery import plugin_router



router = APIRouter(
    prefix="/strategy",
    tags=["Legal Strategy"],
    responses={404: {"description": "Not found"}},
)
plugin_router("complaint")(router)

# Initialize strategy advisor service
strategy_advisor = StrategyAdvisor()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# @plugin complaint
@router.post(
    "/generate",
    response_model=StrategyResponse,
    operation_id="strategy_generate",
    summary="Generate Legal Strategy",
)
def generate_legal_strategy(request: StrategyRequest):
    db = next(get_db())
    try:
        # Process facts from the request.
        facts_for_analysis = []
        for fact_item in request.facts:
            if isinstance(fact_item, int):
                # Retrieve fact from database by ID.
                db_fact = db.query(Fact).filter(Fact.id == fact_item).first()
                if db_fact:
                    facts_for_analysis.append(
                        {
                            "text": db_fact.text,
                            "date": db_fact.date,
                            "tags": db_fact.tags,
                        }
                    )
            elif isinstance(fact_item, dict) and "text" in fact_item:
                facts_for_analysis.append(fact_item)

        if not facts_for_analysis:
            raise HTTPException(
                status_code=400, detail="No valid facts provided for analysis"
            )

        # Process causes of action
        causes_of_action = []
        if request.causes_of_action:
            for cause_name in request.causes_of_action:
                db_cause = (
                    db.query(CauseOfAction)
                    .filter(CauseOfAction.name == cause_name)
                    .first()
                )
                if db_cause:
                    elements = [
                        {"name": element.name, "description": element.description}
                        for element in db_cause.elements
                    ]
                    causes_of_action.append(
                        {
                            "name": db_cause.name,
                            "description": db_cause.description,
                            "elements": elements,
                        }
                    )

        # Generate the strategy using strategy_advisor service
        strategy = strategy_advisor.generate_strategy(
            facts=facts_for_analysis,
            causes_of_action=causes_of_action,
            opposing_arguments=request.opposing_arguments,
            case_phase=request.case_phase,
        )

        return strategy
    finally:
        db.close()


# @plugin complaint
@router.post(
    "/analyze-case-phase",
    response_model=StrategyResponse,
    operation_id="strategy_analyze_case_phase",
    summary="Analyze Case Phase",
)
async def analyze_case_phase(
    request: AnalyzeCasePhaseRequest, db: Session = Depends(get_db)
):
    """
    Analyze case facts to determine the optimal legal strategy for the current or upcoming case phase.
    """
    # If current phase not provided, try to infer from facts
    phase_to_analyze = request.current_phase or "initial"

    # Generate strategy focused on the specific phase
    strategy = strategy_advisor.generate_strategy(
        facts=request.facts,
        case_phase=phase_to_analyze,
        causes_of_action=[],
        opposing_arguments=[],
    )

    # Return the strategy response directly since it matches the AnalyzeCasePhaseResponse model
    return AnalyzeCasePhaseResponse(
        overall_assessment=strategy["overall_assessment"],
        priority_actions=strategy["priority_actions"],
        evidence_strategy=strategy["evidence_strategy"],
        argument_development=strategy["argument_development"],
        potential_motions=strategy["potential_motions"],
        settlement_considerations=strategy["settlement_considerations"],
        statutesReferenced=strategy.get("statutesReferenced", []),
        causesOfAction=strategy.get("causesOfAction", {}),
        opposingArguments=strategy.get("opposingArguments", None),
    )


# @plugin complaint
@router.get(
    "/files",
    response_model=List[str],
    operation_id="strategy_list_files",
    summary="List Files",
)
async def list_files():
    """
    List all uploaded files in the strategy directory.
    """
    try:
        files = os.listdir(UPLOAD_DIR)
        return files
    except Exception as e:
        logger.error(f"Error listing files: {str(e)}")
        raise HTTPException(status_code=500, detail="Error listing files")


# @plugin complaint
@router.delete(
    "/files/{filename}", operation_id="strategy_delete_file", summary="Delete File"
)
async def delete_file(filename: str):
    """
    Delete a specific file from the strategy directory.
    """
    file_path = os.path.join(UPLOAD_DIR, filename)
    try:
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")

        os.remove(file_path)
        return {"message": f"File {filename} successfully deleted"}
    except Exception as e:
        logger.error(f"Error deleting file {filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")
