from __future__ import annotations

from typing import List, Optional

from .base import Agent, function_tool


@function_tool
def add_evidence(file: str, title: str, document_type: str) -> dict:
    """Add evidence record with basic metadata."""
    return {"added": file, "title": title, "type": document_type}


@function_tool
def upload_evidence(file: str, title: str, document_type: str) -> dict:
    """Upload a single evidence file."""
    return {"uploaded": file, "title": title, "type": document_type}


@function_tool
def upload_multiple_evidence(files: List[str]) -> dict:
    """Upload multiple evidence files."""
    return {"uploaded": files}


@function_tool
def process_directory(directory: str) -> dict:
    """Process all evidence files in a directory."""
    return {"processed_dir": directory}


@function_tool
def list_facts() -> list:
    """Return a list of known facts."""
    return []


@function_tool
def extract_facts(text: str) -> list:
    """Extract facts from raw text."""
    return []


@function_tool
def add_fact(fact_text: str, related_claims: Optional[List[str]] = None) -> dict:
    """Add a fact with optional related claims."""
    return {"fact": fact_text, "claims": related_claims or []}


@function_tool
def get_fact(fact_id: int) -> dict:
    """Retrieve a fact by its ID."""
    return {"fact_id": fact_id}


@function_tool
def update_fact(fact_id: int, fact_text: str) -> dict:
    """Update an existing fact."""
    return {"updated": fact_id, "text": fact_text}


@function_tool
def delete_fact(fact_id: int) -> dict:
    """Delete a fact by ID."""
    return {"deleted": fact_id}


@function_tool
def link_fact_to_causes(fact_element_link_id: int, cause_ids: List[int]) -> dict:
    """Link a fact to one or more causes of action."""
    return {"link": fact_element_link_id, "causes": cause_ids}


class EvidenceAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            name="Evidence Agent",
            instructions="Manage evidence and facts: upload, extract, link.",
            tools=[
                add_evidence,
                upload_evidence,
                upload_multiple_evidence,
                process_directory,
                list_facts,
                extract_facts,
                add_fact,
                get_fact,
                update_fact,
                delete_fact,
                link_fact_to_causes,
            ],
        )
