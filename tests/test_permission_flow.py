from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class PermissionFlowTest(unittest.TestCase):
    def test_permissioned_tool_not_executed_when_callback_rejects(self) -> None:
        from min_agent.agent_loop import AgentLoop
        from min_agent.context_builder import ContextBuilder
        from min_agent.tool_registry import ToolRegistry
        from min_agent.trace_recorder import TraceRecorder
        from min_agent.types import AgentAction, AgentContext, ToolResult, ToolSpec

        tool_calls: list[dict] = []

        def handler(args: dict) -> ToolResult:
            tool_calls.append(args)
            return ToolResult(success=True, content="written")

        class WriteRequestModel:
            def decide(self, context: AgentContext) -> AgentAction:
                if not context.observations:
                    return AgentAction.tool_call(
                        "write_file",
                        {"path": "summary.md", "content": "hello"},
                        "need to write summary",
                    )
                return AgentAction.final_answer("rejected", "user said no", success=False)

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            registry = ToolRegistry()
            registry.register(
                ToolSpec(name="write_file", description="Write file", requires_permission=True),
                handler,
            )
            recorder = TraceRecorder(user_goal="write summary.md", workspace=str(workspace))
            loop = AgentLoop(
                context_builder=ContextBuilder(),
                llm=WriteRequestModel(),
                tools=registry,
                recorder=recorder,
                workspace=str(workspace),
                max_turns=3,
                step_delay_seconds=0,
                permission_callback=lambda _action: False,
            )

            result = loop.run("write summary.md")

        self.assertFalse(result.success)
        self.assertEqual(tool_calls, [])

    def test_permission_rejection_emits_permission_requested(self) -> None:
        from min_agent.agent_loop import AgentLoop
        from min_agent.context_builder import ContextBuilder
        from min_agent.tool_registry import ToolRegistry
        from min_agent.trace_recorder import TraceRecorder
        from min_agent.types import AgentAction, AgentContext, ToolResult, ToolSpec

        class WriteRequestModel:
            def decide(self, context: AgentContext) -> AgentAction:
                if not context.observations:
                    return AgentAction.tool_call(
                        "write_file",
                        {"path": "summary.md", "content": "hello"},
                        "need to write summary",
                    )
                return AgentAction.final_answer("rejected", "user said no")

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            registry = ToolRegistry()
            registry.register(
                ToolSpec(name="write_file", description="Write file", requires_permission=True),
                lambda args: ToolResult(success=True, content="written"),
            )
            recorder = TraceRecorder(user_goal="write summary.md", workspace=str(workspace))
            loop = AgentLoop(
                context_builder=ContextBuilder(),
                llm=WriteRequestModel(),
                tools=registry,
                recorder=recorder,
                workspace=str(workspace),
                max_turns=3,
                step_delay_seconds=0,
                permission_callback=lambda _action: False,
            )

            loop.run("write summary.md")

        phases = [event.phase for event in recorder.history()]
        self.assertIn("permission_requested", phases)
        self.assertIn("permission_resolved", phases)

    def test_permission_rejection_emits_permission_resolved_with_approved_false(self) -> None:
        from min_agent.agent_loop import AgentLoop
        from min_agent.context_builder import ContextBuilder
        from min_agent.tool_registry import ToolRegistry
        from min_agent.trace_recorder import TraceRecorder
        from min_agent.types import AgentAction, AgentContext, ToolResult, ToolSpec

        class WriteRequestModel:
            def decide(self, context: AgentContext) -> AgentAction:
                if not context.observations:
                    return AgentAction.tool_call(
                        "write_file",
                        {"path": "summary.md", "content": "hello"},
                        "need to write",
                    )
                return AgentAction.final_answer("ok", "done")

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            registry = ToolRegistry()
            registry.register(
                ToolSpec(name="write_file", description="Write file", requires_permission=True),
                lambda args: ToolResult(success=True, content="written"),
            )
            recorder = TraceRecorder(user_goal="write summary.md", workspace=str(workspace))
            loop = AgentLoop(
                context_builder=ContextBuilder(),
                llm=WriteRequestModel(),
                tools=registry,
                recorder=recorder,
                workspace=str(workspace),
                max_turns=3,
                step_delay_seconds=0,
                permission_callback=lambda _action: False,
            )

            loop.run("write summary.md")

        resolved = [
            event for event in recorder.history() if event.phase == "permission_resolved"
        ]
        self.assertEqual(len(resolved), 1)
        self.assertFalse(resolved[0].output["approved"])

    def test_rejection_creates_observation_with_permission_rejected(self) -> None:
        from min_agent.agent_loop import AgentLoop
        from min_agent.context_builder import ContextBuilder
        from min_agent.tool_registry import ToolRegistry
        from min_agent.trace_recorder import TraceRecorder
        from min_agent.types import AgentAction, AgentContext, ToolResult, ToolSpec

        class WriteRequestModel:
            def decide(self, context: AgentContext) -> AgentAction:
                if not context.observations:
                    return AgentAction.tool_call(
                        "write_file",
                        {"path": "summary.md", "content": "hello"},
                        "need to write",
                    )
                return AgentAction.final_answer("ok", "done")

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            registry = ToolRegistry()
            registry.register(
                ToolSpec(name="write_file", description="Write file", requires_permission=True),
                lambda args: ToolResult(success=True, content="written"),
            )
            recorder = TraceRecorder(user_goal="write summary.md", workspace=str(workspace))
            loop = AgentLoop(
                context_builder=ContextBuilder(),
                llm=WriteRequestModel(),
                tools=registry,
                recorder=recorder,
                workspace=str(workspace),
                max_turns=3,
                step_delay_seconds=0,
                permission_callback=lambda _action: False,
            )

            loop.run("write summary.md")

        observations = [
            event for event in recorder.history() if event.phase == "observation_added"
        ]
        self.assertEqual(len(observations), 1)
        obs = observations[0].output
        self.assertEqual(obs["tool_name"], "write_file")
        self.assertFalse(obs["result"]["success"])
        self.assertEqual(obs["result"]["metadata"]["permission"], "rejected")

    def test_approved_permission_executes_write_file(self) -> None:
        from min_agent.agent_loop import AgentLoop
        from min_agent.context_builder import ContextBuilder
        from min_agent.tool_registry import ToolRegistry
        from min_agent.trace_recorder import TraceRecorder
        from min_agent.types import AgentAction, AgentContext, ToolResult, ToolSpec

        class WriteRequestModel:
            def decide(self, context: AgentContext) -> AgentAction:
                if not context.observations:
                    return AgentAction.tool_call(
                        "write_file",
                        {"path": "summary.md", "content": "hello"},
                        "need to write",
                    )
                return AgentAction.final_answer("wrote file", "done", success=True)

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            registry = ToolRegistry()
            registry.register(
                ToolSpec(name="write_file", description="Write file", requires_permission=True),
                lambda args: ToolResult(success=True, content="wrote file: summary.md"),
            )
            recorder = TraceRecorder(user_goal="write summary.md", workspace=str(workspace))
            loop = AgentLoop(
                context_builder=ContextBuilder(),
                llm=WriteRequestModel(),
                tools=registry,
                recorder=recorder,
                workspace=str(workspace),
                max_turns=3,
                step_delay_seconds=0,
                permission_callback=lambda _action: True,
            )

            result = loop.run("write summary.md")

        self.assertTrue(result.success)
        self.assertIn("wrote file", result.message)

    def test_approved_permission_emits_permission_resolved_with_approved_true(self) -> None:
        from min_agent.agent_loop import AgentLoop
        from min_agent.context_builder import ContextBuilder
        from min_agent.tool_registry import ToolRegistry
        from min_agent.trace_recorder import TraceRecorder
        from min_agent.types import AgentAction, AgentContext, ToolResult, ToolSpec

        class WriteRequestModel:
            def decide(self, context: AgentContext) -> AgentAction:
                if not context.observations:
                    return AgentAction.tool_call(
                        "write_file",
                        {"path": "summary.md", "content": "hello"},
                        "need to write",
                    )
                return AgentAction.final_answer("ok", "done")

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            registry = ToolRegistry()
            registry.register(
                ToolSpec(name="write_file", description="Write file", requires_permission=True),
                lambda args: ToolResult(success=True, content="written"),
            )
            recorder = TraceRecorder(user_goal="write summary.md", workspace=str(workspace))
            loop = AgentLoop(
                context_builder=ContextBuilder(),
                llm=WriteRequestModel(),
                tools=registry,
                recorder=recorder,
                workspace=str(workspace),
                max_turns=3,
                step_delay_seconds=0,
                permission_callback=lambda _action: True,
            )

            loop.run("write summary.md")

        resolved = [
            event for event in recorder.history() if event.phase == "permission_resolved"
        ]
        self.assertEqual(len(resolved), 1)
        self.assertTrue(resolved[0].output["approved"])

    def test_non_permission_tools_execute_without_callback(self) -> None:
        from min_agent.agent_loop import AgentLoop
        from min_agent.context_builder import ContextBuilder
        from min_agent.tool_registry import ToolRegistry
        from min_agent.trace_recorder import TraceRecorder
        from min_agent.types import AgentAction, AgentContext, ToolResult, ToolSpec

        class ReadRequestModel:
            def decide(self, context: AgentContext) -> AgentAction:
                if not context.observations:
                    return AgentAction.tool_call(
                        "read_file",
                        {"path": "notes.md"},
                        "need to read file",
                    )
                return AgentAction.final_answer("done", "read complete")

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "notes.md").write_text("content", encoding="utf-8")
            registry = ToolRegistry()
            registry.register(
                ToolSpec(name="read_file", description="Read file", requires_permission=False),
                lambda args: ToolResult(success=True, content="content"),
            )
            recorder = TraceRecorder(user_goal="read notes.md", workspace=str(workspace))
            loop = AgentLoop(
                context_builder=ContextBuilder(),
                llm=ReadRequestModel(),
                tools=registry,
                recorder=recorder,
                workspace=str(workspace),
                max_turns=3,
                step_delay_seconds=0,
                permission_callback=lambda _action: False,
            )

            result = loop.run("read notes.md")

        self.assertTrue(result.success)
        permissions = [
            event for event in recorder.history() if event.phase == "permission_requested"
        ]
        self.assertEqual(permissions, [])

    def test_permission_preview_ignores_non_string_content_without_crashing(self) -> None:
        from min_agent.agent_loop import AgentLoop
        from min_agent.context_builder import ContextBuilder
        from min_agent.tool_registry import ToolRegistry
        from min_agent.tools.workspace import write_file
        from min_agent.trace_recorder import TraceRecorder
        from min_agent.types import AgentAction, AgentContext, ToolSpec

        class InvalidWriteModel:
            def decide(self, context: AgentContext) -> AgentAction:
                if not context.observations:
                    return AgentAction.tool_call(
                        "write_file",
                        {"path": "summary.md", "content": 123},
                        "model returned invalid write content",
                    )
                return AgentAction.final_answer(
                    "write failed visibly",
                    "invalid content was observed",
                    success=False,
                )

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            registry = ToolRegistry()
            registry.register(
                ToolSpec(name="write_file", description="Write file", requires_permission=True),
                lambda args: write_file(workspace, args),
            )
            recorder = TraceRecorder(user_goal="write summary.md", workspace=str(workspace))
            loop = AgentLoop(
                context_builder=ContextBuilder(),
                llm=InvalidWriteModel(),
                tools=registry,
                recorder=recorder,
                workspace=str(workspace),
                max_turns=3,
                step_delay_seconds=0,
                permission_callback=lambda _action: True,
            )

            result = loop.run("write summary.md")

        self.assertFalse(result.success)
        permission_requests = [
            event for event in recorder.history() if event.phase == "permission_requested"
        ]
        self.assertEqual(permission_requests[0].input["preview"], "")
        tool_finished = [
            event for event in recorder.history() if event.phase == "tool_finished"
        ]
        self.assertEqual(tool_finished[0].status, "failed")
        self.assertIn("content must be a string", tool_finished[0].output["error"])


if __name__ == "__main__":
    unittest.main()
