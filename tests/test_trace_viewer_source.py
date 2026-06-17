from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TraceViewerSourceTest(unittest.TestCase):
    def test_eventsource_error_does_not_override_terminal_status(self) -> None:
        source = (ROOT / "web" / "trace_viewer.js").read_text(encoding="utf-8")

        self.assertIn("function isTerminalStatus", source)
        self.assertIn("if (!isTerminalStatus(state.status))", source)


if __name__ == "__main__":
    unittest.main()
