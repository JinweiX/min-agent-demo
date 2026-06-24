from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


ActionKind = Literal["tool_call", "final_answer"]
EventPhase = Literal[
    "run_started",
    "context_built",
    "llm_decision",
    "tool_started",
    "tool_finished",
    "observation_added",
    "permission_requested",
    "permission_resolved",
    "final_answer",
    "run_completed",
    "run_failed",
    "run_interrupted",
]
EventStatus = Literal["waiting", "running", "completed", "failed", "interrupted", "info"]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args_schema: dict[str, Any] = field(default_factory=dict)
    requires_permission: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ToolResult:
    success: bool
    content: str = ""
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Observation:
    tool_name: str
    args: dict[str, Any]
    result: ToolResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "args": self.args,
            "result": self.result.to_dict(),
        }


@dataclass(frozen=True)
class AgentAction:
    kind: ActionKind
    reason: str
    success: bool = True
    tool_name: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def tool_call(
        cls,
        tool_name: str,
        args: dict[str, Any],
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> AgentAction:
        return cls(kind="tool_call", tool_name=tool_name, args=args, reason=reason, metadata=metadata or {})

    @classmethod
    def final_answer(
        cls,
        message: str,
        reason: str,
        success: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> AgentAction:
        return cls(kind="final_answer", message=message, reason=reason, success=success, metadata=metadata or {})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentContext:
    user_goal: str
    workspace: str
    available_tools: list[ToolSpec]
    observations: list[Observation]

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_goal": self.user_goal,
            "workspace": self.workspace,
            "available_tools": [tool.to_dict() for tool in self.available_tools],
            "observations": [observation.to_dict() for observation in self.observations],
        }


@dataclass(frozen=True)
class AgentRunResult:
    message: str
    success: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TraceEvent:
    run_id: str
    step: int
    timestamp: str
    phase: EventPhase
    status: EventStatus
    title: str
    reason: str = ""
    input: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
