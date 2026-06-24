# Min Agent Demo V0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first usable version of `min-agent-demo`: a minimal observable Agent loop that uses FakeLLM, reads a file from a bounded workspace, streams trace events to a local browser viewer, saves the run record, and exits with a final answer.

**Architecture:** Keep the Agent core real and the intelligence fake. `AgentLoop` owns the loop, `FakeLLM` owns deterministic context-based decisions, tools are invoked only through `ToolRegistry`, observations update context, and trace events are emitted from every meaningful transition. The browser viewer is read-only and receives events through SSE; it never controls the Agent.

**Tech Stack:** Python 3.10+ standard library, `unittest`, `argparse`, `dataclasses`, `pathlib`, `json`, `http.server`, `threading`, `queue`, vanilla HTML/CSS/JavaScript with `EventSource`.

---

## 0. Scope And Non-Goals

### In Scope

- FakeLLM decision rules based on context and observations.
- Agent loop with max-turn protection.
- Workspace-safe `read_file` tool.
- Tool registry and tool specs.
- Context builder.
- Structured trace events.
- Local run record saved as JSON.
- SSE trace server with history replay.
- Browser trace viewer with status, timeline, current detail, and final answer.
- CLI integration.
- Unit tests for core behavior and focused integration tests.

### Out Of Scope

- Real model SDKs.
- API keys, `.env`, `.env.example`.
- File writes.
- Command execution.
- Page-side Agent control.
- Pause, resume, interrupt buttons.
- MCP, hooks, memory, multi-agent.
- Frontend framework or build step.

### Development Red Lines

- Do not hardcode the 7 expected UI steps as execution logic.
- Do not let `AgentLoop` know about `notes.md`.
- Do not call `read_file` directly from `AgentLoop`; use `ToolRegistry`.
- Do not advance the loop using step number.
- Do not let Trace Viewer mutate Agent state.
- Do not read outside the workspace.
- Do not introduce non-standard dependencies in V0.1.
- Do not commit unless the user explicitly confirms.

---

## 1. Target File Structure

Create or modify these files:

```text
src/min_agent/
  __init__.py
  cli.py
  types.py
  context_builder.py
  fake_llm.py
  tool_registry.py
  agent_loop.py
  trace_recorder.py
  trace_server.py
  tools/
    __init__.py
    workspace.py

web/
  trace_viewer.html
  trace_viewer.css
  trace_viewer.js

tests/
  test_project_structure.py
  test_types.py
  test_workspace_tools.py
  test_tool_registry.py
  test_context_builder.py
  test_fake_llm.py
  test_trace_recorder.py
  test_agent_loop.py
  test_trace_server.py
  test_cli.py
```

Existing files to keep in place:

- `AGENTS.md`
- `README.md`
- `docs/runbook.md`
- `最小 Agent Demo 技术方案规划.md`
- `方案审核意见.md`

---

## 2. Data Model Design

### Core Types

`src/min_agent/types.py` should define small dataclasses and literals. These types are the contract between modules.

```python
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

    @classmethod
    def tool_call(cls, tool_name: str, args: dict[str, Any], reason: str) -> "AgentAction":
        return cls(kind="tool_call", tool_name=tool_name, args=args, reason=reason)

    @classmethod
    def final_answer(cls, message: str, reason: str, success: bool = True) -> "AgentAction":
        return cls(kind="final_answer", message=message, reason=reason, success=success)

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
```

### Why These Types Matter

- `AgentAction` is how FakeLLM or a future real LLM tells the loop what to do.
- `Observation` is the only way tool results enter context.
- `ToolSpec` is what the decision layer sees about available tools.
- `TraceEvent` is shared by live streaming and saved run records.

---

## 3. Runtime Flow

V0.1 runtime should follow this loop:

```text
CLI validates workspace
-> TraceRecorder creates run_id
-> TraceServer starts before AgentLoop
-> Browser opens viewer URL
-> AgentLoop emits run_started
-> ContextBuilder builds AgentContext
-> AgentLoop emits context_built
-> FakeLLM decides AgentAction from AgentContext
-> AgentLoop emits llm_decision
-> If action is tool_call:
     ToolRegistry invokes tool
     AgentLoop emits tool_started and tool_finished
     AgentLoop appends Observation
     AgentLoop emits observation_added
     Loop continues
-> If action is final_answer:
     AgentLoop emits final_answer and run_completed
     TraceRecorder saves JSON
     CLI prints summary and viewer URL
```

The expected demo timeline is an outcome of this flow. It is not execution logic.

---

## 4. Implementation Tasks

### Task 1: Core Types

**Files:**
- Create: `src/min_agent/types.py`
- Create: `tests/test_types.py`
- Modify: `tests/test_project_structure.py`

- [ ] **Step 1: Write tests for serializable core types**

Create `tests/test_types.py`:

```python
from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class CoreTypesTest(unittest.TestCase):
    def test_agent_action_tool_call_is_serializable(self) -> None:
        from min_agent.types import AgentAction

        action = AgentAction.tool_call(
            tool_name="read_file",
            args={"path": "notes.md"},
            reason="需要读取文件内容后才能总结",
        )

        self.assertEqual(action.kind, "tool_call")
        self.assertEqual(action.to_dict()["tool_name"], "read_file")
        self.assertEqual(action.to_dict()["args"], {"path": "notes.md"})

    def test_observation_wraps_tool_result(self) -> None:
        from min_agent.types import Observation, ToolResult

        observation = Observation(
            tool_name="read_file",
            args={"path": "notes.md"},
            result=ToolResult(success=True, content="hello"),
        )

        data = observation.to_dict()
        self.assertTrue(data["result"]["success"])
        self.assertEqual(data["result"]["content"], "hello")

    def test_trace_event_is_serializable(self) -> None:
        from min_agent.types import TraceEvent

        event = TraceEvent(
            run_id="run-1",
            step=1,
            timestamp="2026-06-17T16:00:00+08:00",
            phase="llm_decision",
            status="running",
            title="决定下一步",
            reason="还没有文件内容",
            input={"observations": []},
            output={"action": "read_file"},
        )

        data = event.to_dict()
        self.assertEqual(data["phase"], "llm_decision")
        self.assertEqual(data["output"]["action"], "read_file")

    def test_agent_run_result_is_serializable(self) -> None:
        from min_agent.types import AgentRunResult

        result = AgentRunResult(message="done", success=True)

        self.assertEqual(result.to_dict(), {"message": "done", "success": True})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
python3 -m unittest tests.test_types
```

Expected before implementation: import failure for `min_agent.types`.

- [ ] **Step 3: Implement `src/min_agent/types.py`**

Use the complete `types.py` code from section 2.

- [ ] **Step 4: Add `src/min_agent/types.py` to structure test**

In `tests/test_project_structure.py`, add:

```python
"src/min_agent/types.py",
```

to `required_paths`.

- [ ] **Step 5: Verify**

Run:

```bash
python3 -m unittest tests.test_types
python3 -m unittest discover -s tests
```

Expected: all tests pass.

---

### Task 2: Workspace Path Safety And `read_file`

**Files:**
- Create: `src/min_agent/tools/__init__.py`
- Create: `src/min_agent/tools/workspace.py`
- Create: `tests/test_workspace_tools.py`
- Modify: `tests/test_project_structure.py`

- [ ] **Step 1: Write tests for workspace boundaries**

Create `tests/test_workspace_tools.py`:

```python
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class WorkspaceToolsTest(unittest.TestCase):
    def test_read_file_success_inside_workspace(self) -> None:
        from min_agent.tools.workspace import read_file

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "notes.md").write_text("hello agent", encoding="utf-8")

            result = read_file(workspace, {"path": "notes.md"})

        self.assertTrue(result.success)
        self.assertEqual(result.content, "hello agent")
        self.assertEqual(result.metadata["path"], "notes.md")

    def test_read_file_missing_returns_error(self) -> None:
        from min_agent.tools.workspace import read_file

        with tempfile.TemporaryDirectory() as tmp:
            result = read_file(Path(tmp), {"path": "missing.md"})

        self.assertFalse(result.success)
        self.assertIn("not found", result.error or "")

    def test_read_file_rejects_parent_escape(self) -> None:
        from min_agent.tools.workspace import read_file

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            outside = Path(tmp) / "secret.md"
            outside.write_text("secret", encoding="utf-8")

            result = read_file(workspace, {"path": "../secret.md"})

        self.assertFalse(result.success)
        self.assertIn("outside workspace", result.error or "")

    def test_read_file_rejects_absolute_path_outside_workspace(self) -> None:
        from min_agent.tools.workspace import read_file

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            outside = Path(tmp) / "secret.md"
            outside.write_text("secret", encoding="utf-8")

            result = read_file(workspace, {"path": str(outside)})

        self.assertFalse(result.success)
        self.assertIn("outside workspace", result.error or "")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
python3 -m unittest tests.test_workspace_tools
```

Expected before implementation: import failure for `min_agent.tools.workspace`.

- [ ] **Step 3: Implement workspace utilities**

Create `src/min_agent/tools/__init__.py`:

```python
"""Built-in tools for min-agent-demo."""
```

Create `src/min_agent/tools/workspace.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from min_agent.types import ToolResult


def ensure_workspace(workspace: Path | str) -> Path:
    root = Path(workspace).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"workspace does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"workspace is not a directory: {root}")
    return root


def resolve_inside_workspace(workspace: Path | str, user_path: str) -> Path:
    root = ensure_workspace(workspace)
    candidate = Path(user_path).expanduser()
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()

    if not resolved.is_relative_to(root):
        raise PermissionError(f"path is outside workspace: {user_path}")
    return resolved


def read_file(workspace: Path | str, args: dict[str, Any]) -> ToolResult:
    path_value = args.get("path")
    if not isinstance(path_value, str) or not path_value.strip():
        return ToolResult(success=False, error="path is required")

    try:
        resolved = resolve_inside_workspace(workspace, path_value)
    except (FileNotFoundError, NotADirectoryError, PermissionError) as exc:
        return ToolResult(success=False, error=str(exc), metadata={"path": path_value})

    if not resolved.exists():
        return ToolResult(success=False, error=f"file not found: {path_value}", metadata={"path": path_value})
    if not resolved.is_file():
        return ToolResult(success=False, error=f"path is not a file: {path_value}", metadata={"path": path_value})

    try:
        content = resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ToolResult(success=False, error=f"file is not valid utf-8: {path_value}", metadata={"path": path_value})

    root = ensure_workspace(workspace)
    return ToolResult(
        success=True,
        content=content,
        metadata={
            "path": str(resolved.relative_to(root)),
            "bytes": resolved.stat().st_size,
        },
    )
```

- [ ] **Step 4: Add files to structure test**

Add:

```python
"src/min_agent/tools/__init__.py",
"src/min_agent/tools/workspace.py",
```

to `required_paths`.

- [ ] **Step 5: Verify**

Run:

```bash
python3 -m unittest tests.test_workspace_tools
python3 -m unittest discover -s tests
```

Expected: all tests pass.

---

### Task 3: Tool Registry

**Files:**
- Create: `src/min_agent/tool_registry.py`
- Create: `tests/test_tool_registry.py`
- Modify: `tests/test_project_structure.py`

- [ ] **Step 1: Write tests for registration and dispatch**

Create `tests/test_tool_registry.py`:

```python
from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class ToolRegistryTest(unittest.TestCase):
    def test_register_and_call_tool(self) -> None:
        from min_agent.tool_registry import ToolRegistry
        from min_agent.types import ToolResult, ToolSpec

        registry = ToolRegistry()
        registry.register(
            ToolSpec(name="echo", description="Echo input", args_schema={"text": "string"}),
            lambda args: ToolResult(success=True, content=args["text"]),
        )

        result = registry.call("echo", {"text": "hello"})

        self.assertTrue(result.success)
        self.assertEqual(result.content, "hello")

    def test_unknown_tool_returns_failure(self) -> None:
        from min_agent.tool_registry import ToolRegistry

        registry = ToolRegistry()
        result = registry.call("missing", {})

        self.assertFalse(result.success)
        self.assertIn("unknown tool", result.error or "")

    def test_list_specs_exposes_registered_tools(self) -> None:
        from min_agent.tool_registry import ToolRegistry
        from min_agent.types import ToolResult, ToolSpec

        registry = ToolRegistry()
        registry.register(
            ToolSpec(name="read_file", description="Read file", args_schema={"path": "string"}),
            lambda args: ToolResult(success=True, content="ok"),
        )

        specs = registry.list_specs()

        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].name, "read_file")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
python3 -m unittest tests.test_tool_registry
```

Expected before implementation: import failure for `min_agent.tool_registry`.

- [ ] **Step 3: Implement `ToolRegistry`**

Create `src/min_agent/tool_registry.py`:

```python
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

    def call(self, name: str, args: dict) -> ToolResult:
        handler = self._handlers.get(name)
        if handler is None:
            return ToolResult(success=False, error=f"unknown tool: {name}")
        try:
            return handler(args)
        except Exception as exc:
            return ToolResult(success=False, error=f"tool {name} failed: {exc}")
```

- [ ] **Step 4: Add file to structure test**

Add:

```python
"src/min_agent/tool_registry.py",
```

to `required_paths`.

- [ ] **Step 5: Verify**

Run:

```bash
python3 -m unittest tests.test_tool_registry
python3 -m unittest discover -s tests
```

Expected: all tests pass.

---

### Task 4: Context Builder

**Files:**
- Create: `src/min_agent/context_builder.py`
- Create: `tests/test_context_builder.py`
- Modify: `tests/test_project_structure.py`

- [ ] **Step 1: Write tests for context construction**

Create `tests/test_context_builder.py`:

```python
from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class ContextBuilderTest(unittest.TestCase):
    def test_build_context_contains_goal_workspace_tools_and_observations(self) -> None:
        from min_agent.context_builder import ContextBuilder
        from min_agent.types import Observation, ToolResult, ToolSpec

        builder = ContextBuilder()
        observation = Observation(
            tool_name="read_file",
            args={"path": "notes.md"},
            result=ToolResult(success=True, content="hello"),
        )

        context = builder.build(
            user_goal="请读取 notes.md 并总结",
            workspace="examples/workspace",
            available_tools=[ToolSpec(name="read_file", description="Read file")],
            observations=[observation],
        )

        self.assertEqual(context.user_goal, "请读取 notes.md 并总结")
        self.assertEqual(context.workspace, "examples/workspace")
        self.assertEqual(context.available_tools[0].name, "read_file")
        self.assertEqual(context.observations[0].result.content, "hello")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
python3 -m unittest tests.test_context_builder
```

Expected before implementation: import failure for `min_agent.context_builder`.

- [ ] **Step 3: Implement `ContextBuilder`**

Create `src/min_agent/context_builder.py`:

```python
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
```

- [ ] **Step 4: Add file to structure test**

Add:

```python
"src/min_agent/context_builder.py",
```

to `required_paths`.

- [ ] **Step 5: Verify**

Run:

```bash
python3 -m unittest tests.test_context_builder
python3 -m unittest discover -s tests
```

Expected: all tests pass.

---

### Task 5: FakeLLM Decision Rules

**Files:**
- Create: `src/min_agent/fake_llm.py`
- Create: `tests/test_fake_llm.py`
- Modify: `tests/test_project_structure.py`

- [ ] **Step 1: Write tests for context-based decisions**

Create `tests/test_fake_llm.py`:

```python
from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class FakeLLMTest(unittest.TestCase):
    def test_decides_to_read_target_file_when_content_missing(self) -> None:
        from min_agent.fake_llm import FakeLLM
        from min_agent.types import AgentContext, ToolSpec

        llm = FakeLLM()
        context = AgentContext(
            user_goal="请读取 notes.md 并总结",
            workspace="examples/workspace",
            available_tools=[ToolSpec(name="read_file", description="Read file")],
            observations=[],
        )

        action = llm.decide(context)

        self.assertEqual(action.kind, "tool_call")
        self.assertEqual(action.tool_name, "read_file")
        self.assertEqual(action.args, {"path": "notes.md"})
        self.assertIn("还没有", action.reason)

    def test_final_answer_after_successful_read(self) -> None:
        from min_agent.fake_llm import FakeLLM
        from min_agent.types import AgentContext, Observation, ToolResult, ToolSpec

        llm = FakeLLM()
        context = AgentContext(
            user_goal="请读取 notes.md 并总结",
            workspace="examples/workspace",
            available_tools=[ToolSpec(name="read_file", description="Read file")],
            observations=[
                Observation(
                    tool_name="read_file",
                    args={"path": "notes.md"},
                    result=ToolResult(success=True, content="# 示例笔记\n这是一个 Agent demo。"),
                )
            ],
        )

        action = llm.decide(context)

        self.assertEqual(action.kind, "final_answer")
        self.assertIn("示例笔记", action.message or "")

    def test_final_answer_after_failed_read(self) -> None:
        from min_agent.fake_llm import FakeLLM
        from min_agent.types import AgentContext, Observation, ToolResult, ToolSpec

        llm = FakeLLM()
        context = AgentContext(
            user_goal="请读取 missing.md 并总结",
            workspace="examples/workspace",
            available_tools=[ToolSpec(name="read_file", description="Read file")],
            observations=[
                Observation(
                    tool_name="read_file",
                    args={"path": "missing.md"},
                    result=ToolResult(success=False, error="file not found: missing.md"),
                )
            ],
        )

        action = llm.decide(context)

        self.assertEqual(action.kind, "final_answer")
        self.assertFalse(action.success)
        self.assertIn("读取文件失败", action.message or "")

    def test_cannot_decide_without_file_path(self) -> None:
        from min_agent.fake_llm import FakeLLM
        from min_agent.types import AgentContext, ToolSpec

        llm = FakeLLM()
        context = AgentContext(
            user_goal="请总结一下",
            workspace="examples/workspace",
            available_tools=[ToolSpec(name="read_file", description="Read file")],
            observations=[],
        )

        action = llm.decide(context)

        self.assertEqual(action.kind, "final_answer")
        self.assertFalse(action.success)
        self.assertIn("无法判断", action.message or "")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
python3 -m unittest tests.test_fake_llm
```

Expected before implementation: import failure for `min_agent.fake_llm`.

- [ ] **Step 3: Implement FakeLLM**

Create `src/min_agent/fake_llm.py`:

```python
from __future__ import annotations

import re

from min_agent.types import AgentAction, AgentContext, Observation


FILE_PATTERN = re.compile(r"[\w./-]+\.md")


class FakeLLM:
    def decide(self, context: AgentContext) -> AgentAction:
        target_path = self._extract_target_path(context.user_goal)
        if target_path is None:
            return AgentAction.final_answer(
                message="无法判断需要读取哪个文件。请在任务中提供明确的 .md 文件名。",
                reason="用户目标中没有可识别的 Markdown 文件路径",
                success=False,
            )

        observation = self._find_latest_read_observation(context.observations, target_path)
        if observation is None:
            return AgentAction.tool_call(
                tool_name="read_file",
                args={"path": target_path},
                reason=f"还没有 {target_path} 的内容，需要先读取文件后才能总结",
            )

        if not observation.result.success:
            return AgentAction.final_answer(
                message=f"读取文件失败：{observation.result.error}",
                reason="工具没有返回可用于总结的文件内容",
                success=False,
            )

        return AgentAction.final_answer(
            message=self._preview_content(target_path, observation.result.content),
            reason="已经获得文件内容，可以基于 observation 生成总结",
        )

    def _extract_target_path(self, user_goal: str) -> str | None:
        match = FILE_PATTERN.search(user_goal)
        return match.group(0) if match else None

    def _find_latest_read_observation(
        self,
        observations: list[Observation],
        target_path: str,
    ) -> Observation | None:
        for observation in reversed(observations):
            if observation.tool_name == "read_file" and observation.args.get("path") == target_path:
                return observation
        return None

    def _preview_content(self, target_path: str, content: str) -> str:
        # V0.1 does not test summary quality. This preview makes FakeLLM behavior deterministic.
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if not lines:
            return f"{target_path} 是一个空文件，没有可总结的内容。"
        preview = "；".join(lines[:3])
        return f"{target_path} 的主要内容：{preview}"
```

- [ ] **Step 4: Add file to structure test**

Add:

```python
"src/min_agent/fake_llm.py",
```

to `required_paths`.

- [ ] **Step 5: Verify**

Run:

```bash
python3 -m unittest tests.test_fake_llm
python3 -m unittest discover -s tests
```

Expected: all tests pass.

---

### Task 6: Trace Recorder And Run JSON

**Files:**
- Create: `src/min_agent/trace_recorder.py`
- Create: `tests/test_trace_recorder.py`
- Modify: `tests/test_project_structure.py`

- [ ] **Step 1: Write tests for event emission and saving**

Create `tests/test_trace_recorder.py`:

```python
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class TraceRecorderTest(unittest.TestCase):
    def test_emit_increments_steps_and_notifies_subscribers(self) -> None:
        from min_agent.trace_recorder import TraceRecorder

        received = []
        recorder = TraceRecorder(user_goal="goal", workspace="workspace")
        recorder.subscribe(received.append)

        event = recorder.emit(
            phase="run_started",
            status="running",
            title="收到任务",
            reason="用户提交任务",
        )

        self.assertEqual(event.step, 1)
        self.assertEqual(received[0], event)

    def test_save_writes_json_run_record(self) -> None:
        from min_agent.trace_recorder import TraceRecorder

        with tempfile.TemporaryDirectory() as tmp:
            recorder = TraceRecorder(user_goal="goal", workspace="workspace")
            recorder.emit("run_started", "running", "收到任务")
            path = recorder.save(Path(tmp), status="completed")

            data = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["user_goal"], "goal")
        self.assertEqual(len(data["events"]), 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
python3 -m unittest tests.test_trace_recorder
```

Expected before implementation: import failure for `min_agent.trace_recorder`.

- [ ] **Step 3: Implement TraceRecorder**

Create `src/min_agent/trace_recorder.py`:

```python
from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from min_agent.types import EventPhase, EventStatus, TraceEvent


Subscriber = Callable[[TraceEvent], None]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class TraceRecorder:
    def __init__(self, user_goal: str, workspace: str, run_id: str | None = None) -> None:
        self.run_id = run_id or datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
        self.user_goal = user_goal
        self.workspace = workspace
        self.started_at = now_iso()
        self.ended_at: str | None = None
        self.events: list[TraceEvent] = []
        self._subscribers: list[Subscriber] = []

    def subscribe(self, subscriber: Subscriber) -> None:
        self._subscribers.append(subscriber)

    def history(self) -> list[TraceEvent]:
        return list(self.events)

    def emit(
        self,
        phase: EventPhase,
        status: EventStatus,
        title: str,
        reason: str = "",
        input: dict[str, Any] | None = None,
        output: dict[str, Any] | None = None,
    ) -> TraceEvent:
        event = TraceEvent(
            run_id=self.run_id,
            step=len(self.events) + 1,
            timestamp=now_iso(),
            phase=phase,
            status=status,
            title=title,
            reason=reason,
            input=input or {},
            output=output or {},
        )
        self.events.append(event)
        for subscriber in list(self._subscribers):
            subscriber(event)
        return event

    def save(self, runs_dir: Path | str, status: EventStatus) -> Path:
        self.ended_at = now_iso()
        output_dir = Path(runs_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{self.run_id}.json"
        data = {
            "run_id": self.run_id,
            "status": status,
            "user_goal": self.user_goal,
            "workspace": self.workspace,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "events": [event.to_dict() for event in self.events],
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
```

- [ ] **Step 4: Add file to structure test**

Add:

```python
"src/min_agent/trace_recorder.py",
```

to `required_paths`.

- [ ] **Step 5: Verify**

Run:

```bash
python3 -m unittest tests.test_trace_recorder
python3 -m unittest discover -s tests
```

Expected: all tests pass.

---

### Task 7: Agent Loop

**Files:**
- Create: `src/min_agent/agent_loop.py`
- Create: `tests/test_agent_loop.py`
- Modify: `tests/test_project_structure.py`

- [ ] **Step 1: Write tests for successful loop and failure loop**

Create `tests/test_agent_loop.py`:

```python
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class AgentLoopTest(unittest.TestCase):
    def test_loop_reads_file_and_returns_final_answer(self) -> None:
        from min_agent.agent_loop import AgentLoop
        from min_agent.context_builder import ContextBuilder
        from min_agent.fake_llm import FakeLLM
        from min_agent.tool_registry import ToolRegistry
        from min_agent.tools.workspace import read_file
        from min_agent.trace_recorder import TraceRecorder
        from min_agent.types import ToolSpec

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "notes.md").write_text("# 示例\n这是 Agent demo。", encoding="utf-8")

            registry = ToolRegistry()
            registry.register(
                ToolSpec(name="read_file", description="Read file", args_schema={"path": "string"}),
                lambda args: read_file(workspace, args),
            )
            recorder = TraceRecorder(user_goal="请读取 notes.md 并总结", workspace=str(workspace))
            loop = AgentLoop(
                context_builder=ContextBuilder(),
                llm=FakeLLM(),
                tools=registry,
                recorder=recorder,
                workspace=str(workspace),
                max_turns=5,
                step_delay_seconds=0,
            )

            result = loop.run("请读取 notes.md 并总结")

        self.assertTrue(result.success)
        self.assertIn("notes.md", result.message)
        self.assertTrue(any(event.phase == "tool_finished" for event in recorder.history()))
        self.assertTrue(any(event.phase == "final_answer" for event in recorder.history()))

    def test_loop_stops_when_file_is_missing(self) -> None:
        from min_agent.agent_loop import AgentLoop
        from min_agent.context_builder import ContextBuilder
        from min_agent.fake_llm import FakeLLM
        from min_agent.tool_registry import ToolRegistry
        from min_agent.tools.workspace import read_file
        from min_agent.trace_recorder import TraceRecorder
        from min_agent.types import ToolSpec

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            registry = ToolRegistry()
            registry.register(
                ToolSpec(name="read_file", description="Read file", args_schema={"path": "string"}),
                lambda args: read_file(workspace, args),
            )
            recorder = TraceRecorder(user_goal="请读取 missing.md 并总结", workspace=str(workspace))
            loop = AgentLoop(
                context_builder=ContextBuilder(),
                llm=FakeLLM(),
                tools=registry,
                recorder=recorder,
                workspace=str(workspace),
                max_turns=5,
                step_delay_seconds=0,
            )

            result = loop.run("请读取 missing.md 并总结")

        self.assertFalse(result.success)
        self.assertIn("读取文件失败", result.message)
        self.assertTrue(any(event.status == "failed" for event in recorder.history()))

    def test_loop_stops_at_max_turns(self) -> None:
        from min_agent.agent_loop import AgentLoop
        from min_agent.context_builder import ContextBuilder
        from min_agent.tool_registry import ToolRegistry
        from min_agent.trace_recorder import TraceRecorder
        from min_agent.types import AgentAction, AgentContext, ToolResult, ToolSpec

        class AlwaysToolCallLLM:
            def decide(self, context: AgentContext) -> AgentAction:
                return AgentAction.tool_call(
                    tool_name="echo",
                    args={},
                    reason="测试最大轮次保护",
                )

        registry = ToolRegistry()
        registry.register(
            ToolSpec(name="echo", description="Echo"),
            lambda args: ToolResult(success=True, content="again"),
        )
        recorder = TraceRecorder(user_goal="loop forever", workspace="workspace")
        loop = AgentLoop(
            context_builder=ContextBuilder(),
            llm=AlwaysToolCallLLM(),
            tools=registry,
            recorder=recorder,
            workspace="workspace",
            max_turns=2,
            step_delay_seconds=0,
        )

        result = loop.run("loop forever")

        self.assertFalse(result.success)
        self.assertIn("最大轮次", result.message)
        self.assertTrue(any(event.phase == "run_failed" for event in recorder.history()))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
python3 -m unittest tests.test_agent_loop
```

Expected before implementation: import failure for `min_agent.agent_loop`.

- [ ] **Step 3: Implement `AgentLoop`**

Create `src/min_agent/agent_loop.py`:

```python
from __future__ import annotations

import time

from min_agent.context_builder import ContextBuilder
from min_agent.tool_registry import ToolRegistry
from min_agent.trace_recorder import TraceRecorder
from min_agent.types import AgentRunResult, Observation


class AgentLoop:
    def __init__(
        self,
        context_builder: ContextBuilder,
        llm: object,
        tools: ToolRegistry,
        recorder: TraceRecorder,
        workspace: str,
        max_turns: int = 8,
        step_delay_seconds: float = 0.4,
    ) -> None:
        self.context_builder = context_builder
        self.llm = llm
        self.tools = tools
        self.recorder = recorder
        self.workspace = workspace
        self.max_turns = max_turns
        self.step_delay_seconds = step_delay_seconds
        self.observations: list[Observation] = []

    def run(self, user_goal: str) -> AgentRunResult:
        self.recorder.emit(
            phase="run_started",
            status="running",
            title="收到任务",
            reason="用户提交了一个目标",
            input={"user_goal": user_goal, "workspace": self.workspace},
        )

        for _turn in range(self.max_turns):
            self._pause()
            context = self.context_builder.build(
                user_goal=user_goal,
                workspace=self.workspace,
                available_tools=self.tools.list_specs(),
                observations=self.observations,
            )
            self.recorder.emit(
                phase="context_built",
                status="running",
                title="整理上下文",
                reason="准备用户目标、可用工具和已有观察结果",
                output=context.to_dict(),
            )

            self._pause()
            action = self.llm.decide(context)
            self.recorder.emit(
                phase="llm_decision",
                status="running",
                title="决定下一步",
                reason=action.reason,
                output=action.to_dict(),
            )

            if action.kind == "final_answer":
                message = action.message or ""
                status = "completed" if action.success else "failed"
                self.recorder.emit(
                    phase="final_answer",
                    status=status,
                    title="生成最终回答",
                    reason=action.reason,
                    output={"message": message},
                )
                self.recorder.emit(
                    phase="run_completed" if status == "completed" else "run_failed",
                    status=status,
                    title="任务完成" if status == "completed" else "任务失败",
                    output={"message": message},
                )
                return AgentRunResult(message=message, success=action.success)

            if action.tool_name is None:
                return self._fail("模型返回了工具调用，但没有提供工具名称")

            self._pause()
            self.recorder.emit(
                phase="tool_started",
                status="running",
                title=f"调用工具：{action.tool_name}",
                reason=action.reason,
                input={"tool_name": action.tool_name, "args": action.args},
            )

            result = self.tools.call(action.tool_name, action.args)
            event_status = "completed" if result.success else "failed"
            self.recorder.emit(
                phase="tool_finished",
                status=event_status,
                title=f"工具返回：{action.tool_name}",
                reason="工具执行完成" if result.success else "工具执行失败",
                output=result.to_dict(),
            )

            observation = Observation(tool_name=action.tool_name, args=action.args, result=result)
            self.observations.append(observation)
            self.recorder.emit(
                phase="observation_added",
                status="running",
                title="吸收工具结果",
                reason="把工具结果写回上下文，供下一轮判断使用",
                output=observation.to_dict(),
            )

        return self._fail("达到最大轮次限制，Agent 停止以避免无限循环")

    def _fail(self, message: str) -> AgentRunResult:
        self.recorder.emit(
            phase="run_failed",
            status="failed",
            title="任务失败",
            reason=message,
            output={"message": message},
        )
        return AgentRunResult(message=message, success=False)

    def _pause(self) -> None:
        if self.step_delay_seconds > 0:
            time.sleep(self.step_delay_seconds)
```

- [ ] **Step 4: Add file to structure test**

Add:

```python
"src/min_agent/agent_loop.py",
```

to `required_paths`.

- [ ] **Step 5: Verify**

Run:

```bash
python3 -m unittest tests.test_agent_loop
python3 -m unittest discover -s tests
```

Expected: all tests pass.

---

### Task 8: Trace Server With SSE And History Replay

**Files:**
- Create: `src/min_agent/trace_server.py`
- Create: `tests/test_trace_server.py`
- Modify: `tests/test_project_structure.py`

- [ ] **Step 1: Write tests for port selection and URL**

Create `tests/test_trace_server.py`:

```python
from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class TraceServerTest(unittest.TestCase):
    def test_server_exposes_url_before_start(self) -> None:
        from min_agent.trace_recorder import TraceRecorder
        from min_agent.trace_server import TraceServer

        recorder = TraceRecorder(user_goal="goal", workspace="workspace")
        server = TraceServer(recorder=recorder, web_dir=ROOT / "web", preferred_port=0)

        self.assertTrue(server.url.startswith("http://127.0.0.1:"))

    def test_server_start_and_stop(self) -> None:
        from min_agent.trace_recorder import TraceRecorder
        from min_agent.trace_server import TraceServer

        recorder = TraceRecorder(user_goal="goal", workspace="workspace")
        server = TraceServer(recorder=recorder, web_dir=ROOT / "web", preferred_port=0)
        server.start()
        try:
            self.assertTrue(server.is_running)
        finally:
            server.stop()

        self.assertFalse(server.is_running)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
python3 -m unittest tests.test_trace_server
```

Expected before implementation: import failure for `min_agent.trace_server`.

- [ ] **Step 3: Implement TraceServer**

Create `src/min_agent/trace_server.py`:

```python
from __future__ import annotations

import json
import mimetypes
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from min_agent.trace_recorder import TraceRecorder
from min_agent.types import TraceEvent


class TraceServer:
    def __init__(self, recorder: TraceRecorder, web_dir: Path, preferred_port: int = 8765) -> None:
        self.recorder = recorder
        self.web_dir = web_dir
        self._queues: list[queue.Queue[TraceEvent]] = []
        self._queues_lock = threading.Lock()
        self._server = self._make_server(preferred_port)
        self._thread: threading.Thread | None = None
        self.is_running = False
        self.recorder.subscribe(self._broadcast)

    @property
    def url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}/"

    def start(self) -> None:
        if self.is_running:
            return
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self.is_running = True

    def stop(self) -> None:
        if not self.is_running:
            return
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self.is_running = False

    def _broadcast(self, event: TraceEvent) -> None:
        with self._queues_lock:
            queues = list(self._queues)
        for event_queue in queues:
            event_queue.put(event)

    def _make_server(self, preferred_port: int) -> ThreadingHTTPServer:
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path == "/events":
                    self._handle_events()
                    return
                self._handle_static()

            def log_message(self, format: str, *args: object) -> None:
                return

            def _handle_static(self) -> None:
                relative = "trace_viewer.html" if self.path in {"/", "/index.html"} else self.path.lstrip("/")
                file_path = (outer.web_dir / relative).resolve()
                if not file_path.is_relative_to(outer.web_dir.resolve()) or not file_path.exists():
                    self.send_error(404)
                    return
                content = file_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", mimetypes.guess_type(file_path.name)[0] or "application/octet-stream")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)

            def _handle_events(self) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()

                event_queue: queue.Queue[TraceEvent] = queue.Queue()
                with outer._queues_lock:
                    outer._queues.append(event_queue)
                try:
                    for event in outer.recorder.history():
                        self._write_event(event)
                    while True:
                        event = event_queue.get()
                        self._write_event(event)
                except (BrokenPipeError, ConnectionResetError):
                    return
                finally:
                    with outer._queues_lock:
                        if event_queue in outer._queues:
                            outer._queues.remove(event_queue)

            def _write_event(self, event: TraceEvent) -> None:
                payload = json.dumps(event.to_dict(), ensure_ascii=False)
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()

        ports = [preferred_port] if preferred_port == 0 else list(range(preferred_port, preferred_port + 20))
        last_error: OSError | None = None
        for port in ports:
            try:
                return ThreadingHTTPServer(("127.0.0.1", port), Handler)
            except OSError as exc:
                last_error = exc
        raise OSError(f"could not bind trace server: {last_error}")
```

- [ ] **Step 4: Add file to structure test**

Add:

```python
"src/min_agent/trace_server.py",
```

to `required_paths`.

- [ ] **Step 5: Verify**

Run:

```bash
python3 -m unittest tests.test_trace_server
python3 -m unittest discover -s tests
```

Expected: all tests pass.

---

### Task 9: Trace Viewer Rendering

**Files:**
- Modify: `web/trace_viewer.html`
- Modify: `web/trace_viewer.css`
- Modify: `web/trace_viewer.js`

- [ ] **Step 1: Update viewer behavior requirements**

No Python test is required for DOM rendering in V0.1 because there is no browser test runner. The implementation should be reviewed manually by opening the local viewer during Task 11.

Required viewer behavior:

- Connect to `/events` with `EventSource`.
- Keep an in-memory `events` list.
- Render status from latest event.
- Render timeline from all events.
- Let user click timeline item to inspect event detail.
- Auto-select the latest event as it arrives.
- Render final answer when `phase === "final_answer"`.
- Show `reconnecting` status on SSE error.

- [ ] **Step 2: Replace `web/trace_viewer.js` with structured functions**

Use this structure:

```javascript
const state = {
  status: "waiting",
  events: [],
  selectedStep: null,
};

function connectTraceStream() {
  if (!("EventSource" in window)) {
    setStatus("unsupported");
    return;
  }

  const stream = new EventSource("/events");
  stream.onmessage = (message) => {
    const event = JSON.parse(message.data);
    applyEvent(event);
  };
  stream.onerror = () => {
    setStatus("reconnecting");
  };
}

function applyEvent(event) {
  const existingIndex = state.events.findIndex((item) => item.step === event.step);
  if (existingIndex >= 0) {
    state.events[existingIndex] = event;
  } else {
    state.events.push(event);
  }
  state.selectedStep = event.step;
  state.status = event.status || state.status;
  render();
}

function setStatus(status) {
  state.status = status;
  renderStatus();
}

function selectedEvent() {
  return state.events.find((event) => event.step === state.selectedStep) || null;
}

function render() {
  renderStatus();
  renderTimeline();
  renderDetail();
  renderFinalAnswer();
}

function renderStatus() {
  document.querySelector("#run-status").textContent = state.status;
  const latest = state.events[state.events.length - 1];
  document.querySelector("#current-title").textContent = latest?.title || "等待任务开始";
}

function renderTimeline() {
  const timeline = document.querySelector("#timeline");
  timeline.replaceChildren();

  if (state.events.length === 0) {
    const empty = document.createElement("li");
    empty.className = "empty";
    empty.textContent = "等待 Trace 事件...";
    timeline.append(empty);
    return;
  }

  for (const event of state.events) {
    const item = document.createElement("li");
    item.className = event.step === state.selectedStep ? "active" : "";
    item.innerHTML = `
      <button type="button">
        <span>${event.step}. ${event.title}</span>
        <small>${event.phase} · ${event.status}</small>
      </button>
    `;
    item.querySelector("button").addEventListener("click", () => {
      state.selectedStep = event.step;
      render();
    });
    timeline.append(item);
  }
}

function renderDetail() {
  const event = selectedEvent();
  const detail = document.querySelector("#step-detail");
  detail.textContent = event ? JSON.stringify(event, null, 2) : "暂无事件。";
}

function renderFinalAnswer() {
  const finalEvent = state.events.find((event) => event.phase === "final_answer");
  document.querySelector("#final-answer").textContent =
    finalEvent?.output?.message || "任务完成后展示最终回答。";
}

render();
connectTraceStream();
```

- [ ] **Step 3: Update HTML IDs**

Modify the existing heading in `web/trace_viewer.html` from:

```html
<h1>等待任务开始</h1>
```

to:

```html
<h1 id="current-title">等待任务开始</h1>
```

Also ensure the page includes these IDs:

```html
<h1 id="current-title">等待任务开始</h1>
<span id="run-status" class="badge">waiting</span>
<ol id="timeline" class="timeline"></ol>
<pre id="step-detail">暂无事件。</pre>
<p id="final-answer">任务完成后展示最终回答。</p>
```

- [ ] **Step 4: Update CSS for active timeline item**

Add:

```css
.timeline button {
  width: 100%;
  border: 1px solid #d8dee8;
  border-radius: 6px;
  background: #ffffff;
  padding: 12px;
  text-align: left;
  cursor: pointer;
}

.timeline .active button {
  border-color: #2563eb;
  background: #eff6ff;
}

.timeline small {
  display: block;
  margin-top: 4px;
  color: #667085;
}
```

- [ ] **Step 5: Verify**

Run:

```bash
python3 -m unittest discover -s tests
```

Expected: all Python tests pass. Manual browser verification happens after CLI integration.

---

### Task 10: CLI Integration

**Files:**
- Modify: `.gitignore`
- Modify: `src/min_agent/cli.py`
- Create: `tests/test_cli.py`
- Modify: `tests/test_project_structure.py`
- Modify: `README.md`
- Modify: `docs/runbook.md`

- [ ] **Step 1: Write CLI tests**

Create `tests/test_cli.py`:

```python
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class CliTest(unittest.TestCase):
    def test_cli_runs_without_viewer_and_saves_record(self) -> None:
        from min_agent.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            runs = root / "runs"
            workspace.mkdir()
            (workspace / "notes.md").write_text("# 示例\n这是 demo。", encoding="utf-8")

            exit_code = main([
                "请读取 notes.md 并总结",
                "--workspace",
                str(workspace),
                "--runs-dir",
                str(runs),
                "--no-browser",
                "--no-viewer",
                "--step-delay",
                "0",
            ])

            records = list(runs.glob("*.json"))
            data = json.loads(records[0].read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(records), 1)
        self.assertEqual(data["status"], "completed")

    def test_cli_returns_error_for_missing_workspace(self) -> None:
        from min_agent.cli import main

        exit_code = main([
            "请读取 notes.md 并总结",
            "--workspace",
            "missing-workspace",
            "--no-browser",
            "--no-viewer",
        ])

        self.assertEqual(exit_code, 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run failing tests against old CLI**

Run:

```bash
python3 -m unittest tests.test_cli
```

Expected before implementation: tests fail because CLI does not run AgentLoop or save records.

- [ ] **Step 3: Update existing structure test to avoid browser side effects**

In `tests/test_project_structure.py`, change `test_cli_placeholder_runs_with_example_workspace` to:

```python
    def test_cli_runs_with_example_workspace_without_viewer(self) -> None:
        import tempfile

        from min_agent.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            result = main([
                "请读取 notes.md 并总结",
                "--workspace",
                "examples/workspace",
                "--runs-dir",
                tmp,
                "--no-viewer",
                "--no-browser",
                "--step-delay",
                "0",
            ])

        self.assertEqual(result, 0)
```

This keeps the structure smoke test but prevents unit tests from starting a server or opening a browser.

- [ ] **Step 4: Implement CLI orchestration**

Replace `src/min_agent/cli.py` with:

```python
from __future__ import annotations

import argparse
import time
import webbrowser
from pathlib import Path
from typing import Sequence

from min_agent.agent_loop import AgentLoop
from min_agent.context_builder import ContextBuilder
from min_agent.fake_llm import FakeLLM
from min_agent.tool_registry import ToolRegistry
from min_agent.tools.workspace import ensure_workspace, read_file
from min_agent.trace_recorder import TraceRecorder
from min_agent.trace_server import TraceServer
from min_agent.types import ToolSpec


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="min-agent",
        description="Start the minimal observable agent demo.",
    )
    parser.add_argument("goal", help="User goal for the demo agent.")
    parser.add_argument("--workspace", default="examples/workspace", help="Workspace directory.")
    parser.add_argument("--runs-dir", default="runs", help="Directory for run records.")
    parser.add_argument("--port", type=int, default=8765, help="Preferred trace viewer port. Use 0 to let the OS choose a free port.")
    parser.add_argument("--no-browser", action="store_true", help="Print viewer URL without opening a browser.")
    parser.add_argument("--no-viewer", action="store_true", help="Run without starting the trace server.")
    parser.add_argument("--keep-open-seconds", type=float, default=5, help="Keep viewer server alive after completion.")
    parser.add_argument("--step-delay", type=float, default=0.4, help="Delay between visible steps.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        workspace = ensure_workspace(args.workspace)
    except (FileNotFoundError, NotADirectoryError) as exc:
        print(f"Error: {exc}")
        return 2

    recorder = TraceRecorder(user_goal=args.goal, workspace=str(workspace))
    server: TraceServer | None = None

    try:
        if not args.no_viewer:
            server = TraceServer(
                recorder=recorder,
                web_dir=Path(__file__).resolve().parents[2] / "web",
                preferred_port=args.port,
            )
            server.start()
            print(f"Trace viewer: {server.url}")
            if not args.no_browser:
                opened = webbrowser.open(server.url)
                if not opened:
                    print(f"Open this URL manually: {server.url}")
        else:
            print("Trace viewer disabled.")

        registry = ToolRegistry()
        registry.register(
            ToolSpec(
                name="read_file",
                description="Read a UTF-8 text file inside the configured workspace.",
                args_schema={"path": "string"},
            ),
            lambda tool_args: read_file(workspace, tool_args),
        )

        loop = AgentLoop(
            context_builder=ContextBuilder(),
            llm=FakeLLM(),
            tools=registry,
            recorder=recorder,
            workspace=str(workspace),
            step_delay_seconds=args.step_delay,
        )
        result = loop.run(args.goal)
        record_path = recorder.save(args.runs_dir, status="completed" if result.success else "failed")

        print(result.message)
        print(f"Run record: {record_path}")

        if server is not None and args.keep_open_seconds > 0:
            time.sleep(args.keep_open_seconds)
        return 0
    except KeyboardInterrupt:
        recorder.emit(
            phase="run_interrupted",
            status="interrupted",
            title="任务已中断",
            reason="用户通过 Ctrl+C 中断",
        )
        record_path = recorder.save(args.runs_dir, status="interrupted")
        print(f"Interrupted. Run record: {record_path}")
        return 130
    finally:
        if server is not None:
            server.stop()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Verify `.gitignore` ignores generated run records**

Check `.gitignore` and confirm it contains:

```gitignore
runs/*.json
```

If the line is missing, append it without replacing existing ignore rules. Generated run records are local execution artifacts and should not be committed by default.

Also add this path to `tests/test_project_structure.py`:

```python
".gitignore",
```

- [ ] **Step 6: Update README and runbook commands**

Use:

```bash
PYTHONPATH=src python3 -m min_agent.cli "请读取 notes.md 并总结" --workspace examples/workspace
```

For test-friendly non-browser mode:

```bash
PYTHONPATH=src python3 -m min_agent.cli "请读取 notes.md 并总结" --workspace examples/workspace --no-viewer --no-browser --step-delay 0
```

- [ ] **Step 7: Verify**

Run:

```bash
python3 -m unittest tests.test_cli
python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m min_agent.cli "请读取 notes.md 并总结" --workspace examples/workspace --no-viewer --no-browser --step-delay 0
```

Expected:

- Tests pass.
- CLI prints final summary.
- A JSON run record appears under `runs/`.

---

### Task 11: End-To-End Viewer Verification

**Files:**
- No new files required.
- May modify `web/trace_viewer.*` if visual inspection exposes rendering issues.

- [ ] **Step 1: Run the app with viewer enabled**

Run:

```bash
PYTHONPATH=src python3 -m min_agent.cli "请读取 notes.md 并总结" --workspace examples/workspace --step-delay 0.6 --keep-open-seconds 20
```

Expected:

- CLI prints `Trace viewer: http://127.0.0.1:<port>/`.
- Browser opens, or CLI prints URL for manual opening.
- Timeline updates while the command is running.
- The final answer appears in the final result area.

- [ ] **Step 2: Verify saved run record**

Run:

```bash
ls runs
```

Open the latest JSON record and confirm it includes:

- `run_id`
- `status`
- `user_goal`
- `workspace`
- `started_at`
- `ended_at`
- non-empty `events`
- phases including `run_started`, `context_built`, `llm_decision`, `tool_started`, `tool_finished`, `observation_added`, `final_answer`, `run_completed`

- [ ] **Step 3: Verify missing file path**

Run:

```bash
PYTHONPATH=src python3 -m min_agent.cli "请读取 missing.md 并总结" --workspace examples/workspace --no-viewer --no-browser --step-delay 0
```

Expected:

- CLI does not crash.
- Output contains `读取文件失败`.
- Latest run record has status `failed`.

- [ ] **Step 4: Verify workspace escape rejection**

Run:

```bash
PYTHONPATH=src python3 -m min_agent.cli "请读取 ../方案审核意见.md 并总结" --workspace examples/workspace --no-viewer --no-browser --step-delay 0
```

Expected:

- CLI does not expose file contents outside workspace.
- Output indicates file read failure or path rejection.
- Latest run record records failed tool result.

---

### Task 12: Documentation And Final Test Pass

**Files:**
- Modify: `README.md`
- Modify: `docs/runbook.md`
- Modify: `AGENTS.md` only if implementation command or verification command changed.

- [ ] **Step 1: Update README with actual behavior**

README should include:

- Project purpose.
- First-version scope.
- Normal run command.
- Non-browser test command.
- Test command.
- Explanation that FakeLLM is context-based and replaceable.
- Explanation that viewer is read-only.

- [ ] **Step 2: Update runbook with troubleshooting**

`docs/runbook.md` should include:

- Missing workspace.
- Missing file.
- Port occupied.
- Browser does not open.
- Where run records are stored.
- How to run without viewer.

- [ ] **Step 3: Full verification**

Run:

```bash
python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m min_agent.cli "请读取 notes.md 并总结" --workspace examples/workspace --no-viewer --no-browser --step-delay 0
PYTHONPATH=src python3 -m min_agent.cli "请读取 missing.md 并总结" --workspace examples/workspace --no-viewer --no-browser --step-delay 0
```

Expected:

- Unit tests pass.
- Success task produces final summary.
- Missing-file task produces failure summary, not a crash.
- Run records are saved.

---

## 5. Execution Order

Recommended implementation order:

1. Task 1: Core Types
2. Task 2: Workspace Path Safety And `read_file`
3. Task 3: Tool Registry
4. Task 4: Context Builder
5. Task 5: FakeLLM Decision Rules
6. Task 6: Trace Recorder And Run JSON
7. Task 7: Agent Loop
8. Task 8: Trace Server With SSE And History Replay
9. Task 9: Trace Viewer Rendering
10. Task 10: CLI Integration
11. Task 11: End-To-End Viewer Verification
12. Task 12: Documentation And Final Test Pass

Each task should end with `python3 -m unittest discover -s tests`.

This plan intentionally does not include `git commit` steps because project rules require explicit user confirmation before commits.

---

## 6. Review Checklist

Before implementation starts, review these points:

- The plan keeps real model integration out of V0.1.
- The plan keeps write-file and command execution out of V0.1.
- `AgentLoop` remains generic and does not know about `notes.md`.
- `FakeLLM` is deterministic but context-based.
- `ToolRegistry` is the only tool dispatch path.
- `Observation` is the only way tool output enters context.
- `TraceEvent` powers both live SSE and saved JSON.
- Trace Viewer is read-only.
- Workspace path safety is implemented before any file read.
- Tests cover success, missing file, path escape, unknown tool, trace saving, and CLI non-viewer mode.

---

## 7. Confirmed Defaults

The user accepted these defaults before implementation:

1. **Viewer lifetime after completion**
   - Default: keep server open for 5 seconds.
   - Reason: enough for automated runs; user can set `--keep-open-seconds 20` for manual inspection.

2. **Step delay for visual clarity**
   - Default: `0.4` seconds.
   - Reason: without a small delay, FakeLLM demo may finish before the user sees live progress.

3. **Run records in Git**
   - Default: keep `runs/.gitkeep`, ignore generated JSON run records with `.gitignore`.
   - Implementation: `.gitignore` must include `runs/*.json`; do not replace existing ignore rules.

4. **Failure exit code**
   - Default: CLI returns `0` when the Agent gracefully reports task failure, and `2` only for startup/config errors.
   - Reason: “file missing” is a successful demo of error handling, not a program crash.

Implementation can start task by task after this plan is reviewed.
