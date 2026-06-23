from __future__ import annotations

import sys
import tempfile
import unittest
from unittest import mock
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

    def test_list_dir_success_inside_workspace(self) -> None:
        from min_agent.tools.workspace import list_dir

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            docs = workspace / "docs"
            docs.mkdir()
            (docs / "b.md").write_text("hello", encoding="utf-8")
            (docs / "a.txt").write_text("hi", encoding="utf-8")
            (docs / "subdir").mkdir()

            result = list_dir(workspace, {"path": "docs"})

        self.assertTrue(result.success)
        self.assertEqual(result.content, "a.txt\nb.md\nsubdir/")
        self.assertEqual(
            result.metadata,
            {
                "path": "docs",
                "entries": [
                    {"name": "a.txt", "path": "docs/a.txt", "type": "file", "bytes": 2},
                    {"name": "b.md", "path": "docs/b.md", "type": "file", "bytes": 5},
                    {"name": "subdir", "path": "docs/subdir", "type": "directory"},
                ],
            },
        )

    def test_list_dir_defaults_to_workspace_root(self) -> None:
        from min_agent.tools.workspace import list_dir

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "notes.md").write_text("hello", encoding="utf-8")
            (workspace / "docs").mkdir()

            result = list_dir(workspace, {})
            blank_result = list_dir(workspace, {"path": "   "})

        self.assertTrue(result.success)
        self.assertEqual(result.content, "docs/\nnotes.md")
        self.assertEqual(result.metadata["path"], ".")
        self.assertEqual(blank_result.metadata["path"], ".")
        self.assertEqual(blank_result.content, result.content)

    def test_list_dir_rejects_non_string_path(self) -> None:
        from min_agent.tools.workspace import list_dir

        with tempfile.TemporaryDirectory() as tmp:
            result = list_dir(Path(tmp), {"path": 123})

        self.assertFalse(result.success)
        self.assertIn("path must be a string", result.error or "")

    def test_list_dir_rejects_parent_escape(self) -> None:
        from min_agent.tools.workspace import list_dir

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            outside = Path(tmp) / "outside"
            outside.mkdir()

            result = list_dir(workspace, {"path": "../outside"})

        self.assertFalse(result.success)
        self.assertIn("outside workspace", result.error or "")

    def test_list_dir_rejects_absolute_path_outside_workspace(self) -> None:
        from min_agent.tools.workspace import list_dir

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            outside = Path(tmp) / "outside"
            outside.mkdir()

            result = list_dir(workspace, {"path": str(outside)})

        self.assertFalse(result.success)
        self.assertIn("outside workspace", result.error or "")

    def test_list_dir_rejects_file_path(self) -> None:
        from min_agent.tools.workspace import list_dir

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "notes.md").write_text("hello", encoding="utf-8")

            result = list_dir(workspace, {"path": "notes.md"})

        self.assertFalse(result.success)
        self.assertIn("not a directory", result.error or "")

    def test_list_dir_skips_symlink_escape_entries(self) -> None:
        from min_agent.tools.workspace import list_dir

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            outside = Path(tmp) / "outside"
            outside.mkdir()
            (outside / "secret.md").write_text("secret", encoding="utf-8")
            (workspace / "safe.md").write_text("safe", encoding="utf-8")
            (workspace / "outside-link").symlink_to(outside)

            result = list_dir(workspace, {"path": "."})

        self.assertTrue(result.success)
        self.assertEqual(result.content, "safe.md")
        self.assertEqual(
            result.metadata["entries"],
            [{"name": "safe.md", "path": "safe.md", "type": "file", "bytes": 4}],
        )

    def test_list_dir_skips_entry_when_resolve_fails(self) -> None:
        from min_agent.tools.workspace import list_dir

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            safe = workspace / "safe.md"
            broken = workspace / "broken.md"
            safe.write_text("safe", encoding="utf-8")
            broken.write_text("broken", encoding="utf-8")
            original_resolve = Path.resolve

            def resolve_with_broken_entry(path: Path, *args: object, **kwargs: object) -> Path:
                if path.name == broken.name:
                    raise OSError("cannot resolve entry")
                return original_resolve(path, *args, **kwargs)

            with mock.patch.object(type(broken), "resolve", resolve_with_broken_entry):
                result = list_dir(workspace, {"path": "."})

        self.assertTrue(result.success)
        self.assertEqual(result.content, "safe.md")
        self.assertEqual(
            result.metadata["entries"],
            [{"name": "safe.md", "path": "safe.md", "type": "file", "bytes": 4}],
        )

    def test_list_dir_returns_error_when_iterdir_fails(self) -> None:
        from min_agent.tools.workspace import list_dir

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            docs = workspace / "docs"
            docs.mkdir()
            original_iterdir = Path.iterdir

            def iterdir_with_failure(path: Path) -> object:
                if path.name == docs.name:
                    raise OSError("directory vanished")
                return original_iterdir(path)

            with mock.patch.object(type(docs), "iterdir", iterdir_with_failure):
                result = list_dir(workspace, {"path": "docs"})

        self.assertFalse(result.success)
        self.assertIn("could not list directory", result.error or "")
        self.assertIn("docs", result.error or "")
        self.assertIn("directory vanished", result.error or "")
        self.assertEqual(result.metadata, {"path": "docs"})

    def test_list_dir_skips_entry_from_content_and_metadata_when_stat_fails(self) -> None:
        from min_agent.tools.workspace import list_dir

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            bad = workspace / "bad.md"
            safe = workspace / "safe.md"
            bad.write_text("bad", encoding="utf-8")
            safe.write_text("safe", encoding="utf-8")
            original_resolve = Path.resolve
            original_is_dir = Path.is_dir
            original_is_file = Path.is_file
            original_stat = Path.stat

            def resolve_with_bad_entry(path: Path, *args: object, **kwargs: object) -> Path:
                if path.name == bad.name:
                    return path
                return original_resolve(path, *args, **kwargs)

            def is_dir_with_bad_entry(path: Path, *args: object, **kwargs: object) -> bool:
                if path.name == bad.name:
                    return False
                return original_is_dir(path, *args, **kwargs)

            def is_file_with_bad_entry(path: Path, *args: object, **kwargs: object) -> bool:
                if path.name == bad.name:
                    return True
                return original_is_file(path, *args, **kwargs)

            def stat_with_bad_entry(path: Path, *args: object, **kwargs: object) -> object:
                if path.name == bad.name:
                    raise OSError("cannot stat entry")
                return original_stat(path, *args, **kwargs)

            with (
                mock.patch.object(type(bad), "resolve", resolve_with_bad_entry),
                mock.patch.object(type(bad), "is_dir", is_dir_with_bad_entry),
                mock.patch.object(type(bad), "is_file", is_file_with_bad_entry),
                mock.patch.object(type(bad), "stat", stat_with_bad_entry),
            ):
                result = list_dir(workspace, {"path": "."})

        self.assertTrue(result.success)
        self.assertEqual(result.content, "safe.md")
        self.assertEqual(
            result.metadata["entries"],
            [{"name": "safe.md", "path": "safe.md", "type": "file", "bytes": 4}],
        )


if __name__ == "__main__":
    unittest.main()
