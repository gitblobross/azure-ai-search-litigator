from __future__ import annotations
import requests

from .base import Agent, function_tool


@function_tool
def complaint_submit_feedback(user_question: str, gpt_response: str, user_feedback: str) -> dict:
    """Submit user feedback to the Complaint plugin feedback endpoint."""
    import os

    feedback_url = os.getenv("COMPLAINT_FEEDBACK_API_URL", "http://localhost:9003/feedback")
    payload = {
        "user_question": user_question,
        "gpt_response": gpt_response,
        "user_feedback": user_feedback,
    }

    try:
        resp = requests.post(feedback_url, json=payload)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def submit_feedback(user_question: str, gpt_response: str, user_feedback: str) -> dict:
    """Submit user feedback to the NLP plugin feedback endpoint."""
    import os

    feedback_url = os.getenv("FEEDBACK_API_URL", "http://localhost:9001/feedback")
    payload = {
        "user_question": user_question,
        "gpt_response": gpt_response,
        "user_feedback": user_feedback,
    }
    try:
        resp = requests.post(feedback_url, json=payload)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e)}




@function_tool
def upload_files(files: List[str], document_type: str) -> dict:
    """Upload one or more files."""
    return {"files": files, "type": document_type}


@function_tool
def analyze_legal_docs(text: str) -> dict:
    """Analyze legal documents and return a summary."""
    snippet = text[:75] + ("..." if len(text) > 75 else "")
    return {"summary": snippet}


@function_tool
def health_check() -> dict:
    """Simple health check."""
    return {"ok": True}


@function_tool
def echo(message: str) -> dict:
    """Echo back a provided message."""
    return {"echo": message}


class UtilityAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            name="Utility Agent",
            instructions="Public endpoints and miscellaneous utilities.",
            tools=[upload_files, analyze_legal_docs, health_check, echo],
        )


class ExtendedComplaintAgent(UtilityAgent):
    def __init__(self) -> None:
        super().__init__()
        self.tools.append(complaint_submit_feedback)

class ExtendedUtilityAgent(UtilityAgent):
    def __init__(self) -> None:
        super().__init__()
        self.tools.append(submit_feedback)


class ExtendedComplaintAgent(UtilityAgent):
    def __init__(self) -> None:
        super().__init__()
        self.tools.append(complaint_submit_feedback)

class ExtendedUtilityAgent(UtilityAgent):
    def __init__(self) -> None:
        super().__init__()
        self.tools.append(submit_feedback)
