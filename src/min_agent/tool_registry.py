from __future__ import annotations

from collections.abc import Callable
from typing import Any

from min_agent.types import ToolResult, ToolSpec


ToolHandler = Callable[[dict[str, Any]], ToolResult]


class ToolRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, spec: ToolSpec, handler: ToolHandler) -> None:
        if spec.name in self._handlers:
            raise ValueError(f"tool already registered: {spec.name}")
        self._specs[spec.name] = spec
        self._handlers[spec.name] = handler

    def list_specs(self) -> list[ToolSpec]:
        return list(self._specs.values())

    def call(self, name: str, args: dict[str, Any]) -> ToolResult:
        handler = self._handlers.get(name)
        if handler is None:
            return ToolResult(success=False, error=f"unknown tool: {name}")
        try:
            return handler(args)
        except Exception as exc:
            return ToolResult(success=False, error=f"tool {name} failed: {exc}")
