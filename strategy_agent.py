from typing import List

from .base import Agent, function_tool


@function_tool
def generate_strategy(facts: List[str], case_phase: str = "initial") -> dict:
    """Generate legal strategy guidance based on facts and case phase."""
    return {"phase": case_phase, "facts": facts}


@function_tool
def analyze_case_phase(facts: List[str], current_phase: str) -> dict:
    """Analyze the current case phase and suggest next steps."""
    return {"phase": current_phase}


@function_tool
def list_strategy_files() -> List[str]:
    """List uploaded strategy files."""
    return []


@function_tool
def get_case_timeline() -> dict:
    """Return a generated case timeline."""
    return {"timeline": []}


class StrategyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            name="Strategy Agent",
            instructions="Analyze facts to recommend legal strategy and timelines.",
            tools=[
                generate_strategy,
                analyze_case_phase,
                list_strategy_files,
                get_case_timeline,
            ],
        )
