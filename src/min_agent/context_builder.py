from __future__ import annotations

from min_agent.types import AgentContext, Observation, ToolSpec


class ContextBuilder:
    def build(
        self,
        user_goal: str,
        workspace: str,
        available_tools: list[ToolSpec],
        observations: list[Observation],
    ) -> AgentContext:
        return AgentContext(
            user_goal=user_goal,
            workspace=workspace,
            available_tools=list(available_tools),
            observations=list(observations),
        )
