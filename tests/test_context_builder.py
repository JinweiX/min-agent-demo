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
