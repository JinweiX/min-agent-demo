from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class WorkspaceToolsTest(unittest.TestCase):
    def test_read_file_success_inside_workspace(self) -> None:
        from min_agent.tools.workspace import read_file

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "notes.md").write_text("hello agent", encoding="utf-8")

            result = read_file(workspace, {"path": "notes.md"})

        self.assertTrue(result.success)
        self.assertEqual(result.content, "hello agent")
        self.assertEqual(result.metadata["path"], "notes.md")

    def test_read_file_missing_returns_error(self) -> None:
        from min_agent.tools.workspace import read_file

        with tempfile.TemporaryDirectory() as tmp:
            result = read_file(Path(tmp), {"path": "missing.md"})

        self.assertFalse(result.success)
        self.assertIn("not found", result.error or "")

    def test_read_file_rejects_parent_escape(self) -> None:
        from min_agent.tools.workspace import read_file

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            outside = Path(tmp) / "secret.md"
            outside.write_text("secret", encoding="utf-8")

            result = read_file(workspace, {"path": "../secret.md"})

        self.assertFalse(result.success)
        self.assertIn("outside workspace", result.error or "")

    def test_read_file_rejects_absolute_path_outside_workspace(self) -> None:
        from min_agent.tools.workspace import read_file

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            outside = Path(tmp) / "secret.md"
            outside.write_text("secret", encoding="utf-8")

            result = read_file(workspace, {"path": str(outside)})

        self.assertFalse(result.success)
        self.assertIn("outside workspace", result.error or "")

    def test_read_file_rejects_symlink_escape(self) -> None:
        from min_agent.tools.workspace import read_file

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            outside = Path(tmp) / "secret.md"
            outside.write_text("secret", encoding="utf-8")
            (workspace / "link.md").symlink_to(outside)

            result = read_file(workspace, {"path": "link.md"})

        self.assertFalse(result.success)
        self.assertIn("outside workspace", result.error or "")

    def test_read_file_rejects_blank_path(self) -> None:
        from min_agent.tools.workspace import read_file

        with tempfile.TemporaryDirectory() as tmp:
            result = read_file(Path(tmp), {"path": "   "})

        self.assertFalse(result.success)
        self.assertIn("path is required", result.error or "")

    def test_read_file_rejects_directory(self) -> None:
        from min_agent.tools.workspace import read_file

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "folder").mkdir()

            result = read_file(workspace, {"path": "folder"})

        self.assertFalse(result.success)
        self.assertIn("not a file", result.error or "")


if __name__ == "__main__":
    unittest.main()
