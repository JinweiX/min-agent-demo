from __future__ import annotations

from typing import Protocol

from min_agent.types import AgentAction, AgentContext


class DecisionModel(Protocol):
    def decide(self, context: AgentContext) -> AgentAction:
        ...
