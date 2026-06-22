from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TraceViewerSourceTest(unittest.TestCase):
    def test_eventsource_error_does_not_override_terminal_status(self) -> None:
        source = (ROOT / "web" / "trace_viewer.js").read_text(encoding="utf-8")

        self.assertIn("function isTerminalStatus", source)
        self.assertIn("if (!isTerminalStatus(state.status))", source)

    def test_step_detail_renders_model_call_sections(self) -> None:
        source = (ROOT / "web" / "trace_viewer.js").read_text(encoding="utf-8")

        self.assertIn("function renderModelCall", source)
        self.assertIn("大模型返回 message.content", source)
        self.assertIn("未调用大模型", source)
        self.assertIn("原始事件", source)

    def test_timeline_renders_agent_module_badges(self) -> None:
        source = (ROOT / "web" / "trace_viewer.js").read_text(encoding="utf-8")

        self.assertIn("function moduleForPhase", source)
        self.assertIn("agent-module-badge", source)
        self.assertIn('"context_built": "Context"', source)
        self.assertIn('"llm_decision": "Model / Reasoning"', source)
        self.assertIn('"tool_started": "Tools"', source)
        self.assertIn('"observation_added": "Memory / State"', source)
        self.assertIn('"final_answer": "Agent Loop"', source)


if __name__ == "__main__":
    unittest.main()
