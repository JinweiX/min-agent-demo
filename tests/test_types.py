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
