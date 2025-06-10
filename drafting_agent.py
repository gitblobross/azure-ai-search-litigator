from __future__ import annotations

from typing import List, Optional

from .base import Agent, function_tool


@function_tool
def draft_complaint(section: str, content: str) -> dict:
    """Create a new complaint section draft."""
    return {"section": section, "content": content}


@function_tool
def update_draft(draft_id: int, content: str) -> dict:
    """Update an existing draft section."""
    return {"draft_id": draft_id, "content": content}


@function_tool
def get_draft(draft_id: int) -> dict:
    """Retrieve a draft by ID."""
    return {"draft_id": draft_id}


@function_tool
def list_draft_versions(draft_id: int) -> List[dict]:
    """List saved versions for a draft."""
    return []


@function_tool
def rollback_draft(draft_id: int, version_id: int) -> dict:
    """Rollback a draft to a previous version."""
    return {"draft_id": draft_id, "version": version_id}


@function_tool
def save_gpt_draft(draft: str) -> dict:
    """Persist a GPT-generated draft."""
    return {"saved": True, "draft": draft}


@function_tool
def draft_motion_response(
    facts: List[str], claims: List[str], motion_type: str = "Motion to Dismiss"
) -> dict:
    """Draft a motion response based on provided facts and claims."""
    return {"motion": motion_type}


@function_tool
def draft_settlement_demand(
    facts: List[str], claims: List[str], terms: Optional[str] = None
) -> dict:
    """Draft a settlement demand letter."""
    return {"terms": terms}


class DraftingAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            name="Drafting Agent",
            instructions="Draft, save, and manage legal complaints and motions.",
            tools=[
                draft_complaint,
                update_draft,
                get_draft,
                list_draft_versions,
                rollback_draft,
                save_gpt_draft,
                draft_motion_response,
                draft_settlement_demand,
            ],
        )
