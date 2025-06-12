from __future__ import annotations

from typing import List

from .base import Agent, function_tool


@function_tool
def list_legal_elements() -> List[dict]:
    """List all legal elements grouped by cause."""
    return []


@function_tool
def create_legal_element(name: str, description: str) -> dict:
    """Create a new legal element."""
    return {"name": name, "description": description}


@function_tool
def get_legal_element(element_id: int) -> dict:
    """Retrieve a legal element by ID."""
    return {"element_id": element_id}


@function_tool
def compare_facts_to_elements(facts: List[str]) -> dict:
    """Compare facts to legal elements and return matches."""
    return {"facts": facts}


@function_tool
def compare_legal_elements(element_ids: List[int]) -> dict:
    """Compare multiple legal elements for similarity."""
    return {"elements": element_ids}


class LegalElementAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            name="Legal Elements Agent",
            instructions="Handle creation and analysis of legal elements and causes.",
            tools=[
                list_legal_elements,
                create_legal_element,
                get_legal_element,
                compare_facts_to_elements,
                compare_legal_elements,
            ],
        )
