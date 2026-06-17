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
