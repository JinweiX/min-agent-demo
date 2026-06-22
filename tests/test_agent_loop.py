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

    def test_loop_uses_registry_for_model_tool_call(self) -> None:
        from min_agent.agent_loop import AgentLoop
        from min_agent.context_builder import ContextBuilder
        from min_agent.tool_registry import ToolRegistry
        from min_agent.trace_recorder import TraceRecorder
        from min_agent.types import AgentAction, AgentContext, ToolResult, ToolSpec

        class ToolCallModel:
            def __init__(self) -> None:
                self.calls = 0

            def decide(self, context: AgentContext) -> AgentAction:
                self.calls += 1
                if self.calls == 1:
                    return AgentAction.tool_call("registered_tool", {}, "需要调用注册工具")
                return AgentAction.final_answer("done", "工具已调用")

        registry = ToolRegistry()
        calls = []
        registry.register(
            ToolSpec(name="registered_tool", description="Registered test tool"),
            lambda args: calls.append(args) or ToolResult(success=True, content="ok"),
        )
        recorder = TraceRecorder(user_goal="goal", workspace="workspace")
        loop = AgentLoop(
            context_builder=ContextBuilder(),
            llm=ToolCallModel(),
            tools=registry,
            recorder=recorder,
            workspace="workspace",
            step_delay_seconds=0,
        )

        result = loop.run("goal")

        self.assertTrue(result.success)
        self.assertEqual(calls, [{}])


if __name__ == "__main__":
    unittest.main()
