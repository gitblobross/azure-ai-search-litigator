from __future__ import annotations

from .base import Agent, handoff
from .drafting_agent import DraftingAgent
from .evidence_agent import EvidenceAgent
from .legal_elements_agent import LegalElementAgent
from .rag_agent import RagAgent
from .strategy_agent import StrategyAgent
from .utility_agent import UtilityAgent


class LitigatorOrchestratorAgent(Agent):
    def __init__(self):
        handoffs = [
            EvidenceAgent(),
            DraftingAgent(),
            LegalElementAgent(),
            StrategyAgent(),
            RagAgent(),
            UtilityAgent(),
        ]
        tools = []
        for agent in handoffs:
            tools += agent.tools
        super().__init__(
            name="Litigator Orchestrator Agent",
            instructions="Route requests to the correct agent or handle directly.",
            tools=tools,
            handoffs=[handoff(agent) for agent in handoffs],
        )
