from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


class ProjectStructureTest(unittest.TestCase):
    def test_required_files_exist(self) -> None:
        required_paths = [
            "AGENTS.md",
            "README.md",
            "pyproject.toml",
            "src/min_agent/__init__.py",
            "src/min_agent/cli.py",
            "examples/workspace/notes.md",
            "web/trace_viewer.html",
            "web/trace_viewer.css",
            "web/trace_viewer.js",
            "runs/.gitkeep",
            "docs/runbook.md",
        ]

        for relative_path in required_paths:
            with self.subTest(relative_path=relative_path):
                self.assertTrue((ROOT / relative_path).exists())

    def test_project_rules_keep_agent_loop_extensible(self) -> None:
        rules = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("AgentLoop", rules)
        self.assertIn("FakeLLM", rules)
        self.assertIn("ToolRegistry", rules)
        self.assertIn("不能写死固定 7 步流程", rules)

    def test_cli_placeholder_runs_with_example_workspace(self) -> None:
        from min_agent.cli import main

        result = main(["请读取 notes.md 并总结", "--workspace", "examples/workspace"])

        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()

