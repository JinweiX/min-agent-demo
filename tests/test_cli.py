from __future__ import annotations

import json
import sys
import tempfile
import unittest
from unittest.mock import patch
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

            exit_code = main(
                [
                    "请读取 notes.md 并总结",
                    "--workspace",
                    str(workspace),
                    "--runs-dir",
                    str(runs),
                    "--no-browser",
                    "--no-viewer",
                    "--step-delay",
                    "0",
                ]
            )

            records = list(runs.glob("*.json"))
            data = json.loads(records[0].read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(records), 1)
        self.assertEqual(data["status"], "completed")

    def test_cli_returns_error_for_missing_workspace(self) -> None:
        from min_agent.cli import main

        exit_code = main(
            [
                "请读取 notes.md 并总结",
                "--workspace",
                "missing-workspace",
                "--no-browser",
                "--no-viewer",
            ]
        )

        self.assertEqual(exit_code, 2)

    def test_cli_returns_error_for_workspace_file(self) -> None:
        from min_agent.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            workspace_file = Path(tmp) / "workspace.txt"
            workspace_file.write_text("not a directory", encoding="utf-8")

            exit_code = main(
                [
                    "请读取 notes.md 并总结",
                    "--workspace",
                    str(workspace_file),
                    "--no-browser",
                    "--no-viewer",
                ]
            )

        self.assertEqual(exit_code, 2)

    def test_cli_returns_error_when_viewer_cannot_start(self) -> None:
        from min_agent.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            (workspace / "notes.md").write_text("# 示例", encoding="utf-8")

            with patch("min_agent.cli.TraceServer", side_effect=OSError("bind failed")):
                exit_code = main(
                    [
                        "请读取 notes.md 并总结",
                        "--workspace",
                        str(workspace),
                        "--no-browser",
                    ]
                )

        self.assertEqual(exit_code, 2)

    def test_cli_default_fake_mode_does_not_require_deepseek_key(self) -> None:
        from min_agent.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            runs = root / "runs"
            workspace.mkdir()
            (workspace / "notes.md").write_text("# 示例", encoding="utf-8")

            with patch.dict("os.environ", {}, clear=True):
                exit_code = main(
                    [
                        "请读取 notes.md 并总结",
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

        self.assertEqual(exit_code, 0)

    def test_cli_deepseek_mode_requires_key(self) -> None:
        from min_agent.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            (workspace / "notes.md").write_text("# 示例", encoding="utf-8")

            with patch.dict("os.environ", {}, clear=True):
                exit_code = main(
                    [
                        "请读取 notes.md 并总结",
                        "--workspace",
                        str(workspace),
                        "--decision-model",
                        "deepseek",
                        "--no-viewer",
                        "--no-browser",
                    ]
                )

        self.assertEqual(exit_code, 2)


if __name__ == "__main__":
    unittest.main()
