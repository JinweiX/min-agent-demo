from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def load_single_run_record(runs_dir: Path) -> dict:
    records = list(runs_dir.glob("*.json"))
    if len(records) != 1:
        raise AssertionError(f"expected exactly one run record, got {len(records)}")
    return json.loads(records[0].read_text(encoding="utf-8"))


def phases(record: dict) -> list[str]:
    return [event["phase"] for event in record["events"]]


def tool_started_names(record: dict) -> list[str]:
    return [
        event["input"]["tool_name"]
        for event in record["events"]
        if event["phase"] == "tool_started"
    ]


class CliScenarioTest(unittest.TestCase):
    def test_multi_file_summary_record_shows_discover_read_answer_chain(self) -> None:
        from min_agent.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            runs = root / "runs"
            workspace.mkdir()
            (workspace / "project.md").write_text("# 项目\nmin-agent-demo", encoding="utf-8")
            (workspace / "architecture.md").write_text("# 架构\nAgentLoop", encoding="utf-8")

            exit_code = main(
                [
                    "请阅读这个工作区里的资料，并总结这个 demo 是怎么工作的",
                    "--workspace",
                    str(workspace),
                    "--runs-dir",
                    str(runs),
                    "--no-viewer",
                    "--no-browser",
                    "--step-delay",
                    "0",
                ]
            )
            record = load_single_run_record(runs)

        self.assertEqual(exit_code, 0)
        self.assertEqual(record["status"], "completed")
        self.assertIn("run_started", phases(record))
        self.assertIn("context_built", phases(record))
        self.assertIn("llm_decision", phases(record))
        self.assertIn("observation_added", phases(record))
        self.assertIn("final_answer", phases(record))
        self.assertIn("run_completed", phases(record))
        self.assertIn("list_dir", tool_started_names(record))
        self.assertIn("read_file", tool_started_names(record))

    def test_approved_write_record_shows_permission_before_write_tool_execution(self) -> None:
        from min_agent.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            runs = root / "runs"
            workspace.mkdir()
            (workspace / "project.md").write_text("# 项目\nmin-agent-demo", encoding="utf-8")

            with patch("builtins.input", return_value="y"):
                exit_code = main(
                    [
                        "请阅读这个工作区里的资料，并生成 summary.md",
                        "--workspace",
                        str(workspace),
                        "--runs-dir",
                        str(runs),
                        "--no-viewer",
                        "--no-browser",
                        "--step-delay",
                        "0",
                    ]
                )
            record = load_single_run_record(runs)
            summary_exists = (workspace / "summary.md").exists()

        event_phases = phases(record)
        write_started_index = next(
            index
            for index, event in enumerate(record["events"])
            if event["phase"] == "tool_started"
            and event["input"]["tool_name"] == "write_file"
        )
        permission_requested_index = event_phases.index("permission_requested")
        permission_resolved_index = event_phases.index("permission_resolved")

        self.assertEqual(exit_code, 0)
        self.assertEqual(record["status"], "completed")
        self.assertTrue(summary_exists)
        self.assertLess(permission_requested_index, permission_resolved_index)
        self.assertLess(permission_resolved_index, write_started_index)
        self.assertTrue(record["events"][permission_resolved_index]["output"]["approved"])

    def test_rejected_write_record_never_starts_write_file_tool(self) -> None:
        from min_agent.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            runs = root / "runs"
            workspace.mkdir()
            (workspace / "project.md").write_text("# 项目\nmin-agent-demo", encoding="utf-8")

            with patch("builtins.input", return_value="n"):
                exit_code = main(
                    [
                        "请阅读这个工作区里的资料，并生成 summary.md",
                        "--workspace",
                        str(workspace),
                        "--runs-dir",
                        str(runs),
                        "--no-viewer",
                        "--no-browser",
                        "--step-delay",
                        "0",
                    ]
                )
            record = load_single_run_record(runs)
            summary_exists = (workspace / "summary.md").exists()

        self.assertEqual(exit_code, 0)
        self.assertEqual(record["status"], "failed")
        self.assertFalse(summary_exists)
        self.assertIn("permission_requested", phases(record))
        self.assertIn("permission_resolved", phases(record))
        self.assertFalse(
            next(
                event
                for event in record["events"]
                if event["phase"] == "permission_resolved"
            )["output"]["approved"]
        )
        self.assertNotIn("write_file", tool_started_names(record))


if __name__ == "__main__":
    unittest.main()
