from __future__ import annotations

from .base import Agent, function_tool


@function_tool
def rag_query(query: str, index: str = "evidence", top_k: int = 3) -> dict:
    """Run a retrieval-augmented generation query."""
    return {"query": query, "index": index, "top_k": top_k}


@function_tool
def contradiction_check(text: str) -> dict:
    """Check text for contradictions against known facts."""
    return {"text": text, "contradiction": False}


@function_tool
def discovery_helper(facts: list, claims: list) -> dict:
    """Suggest discovery requests based on facts and claims."""
    return {"facts": facts, "claims": claims}


class RagAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            name="RAG/Discovery Agent",
            instructions="Handle retrieval-augmented generation and discovery tasks.",
            tools=[rag_query, contradiction_check, discovery_helper],
        )
