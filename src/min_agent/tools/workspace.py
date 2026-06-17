from __future__ import annotations

from pathlib import Path
from typing import Any

from min_agent.types import ToolResult


def ensure_workspace(workspace: Path | str) -> Path:
    root = Path(workspace).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"workspace does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"workspace is not a directory: {root}")
    return root


def resolve_inside_workspace(workspace: Path | str, user_path: str) -> Path:
    root = ensure_workspace(workspace)
    candidate = Path(user_path).expanduser()
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()

    if not resolved.is_relative_to(root):
        raise PermissionError(f"path is outside workspace: {user_path}")
    return resolved


def read_file(workspace: Path | str, args: dict[str, Any]) -> ToolResult:
    path_value = args.get("path")
    if not isinstance(path_value, str) or not path_value.strip():
        return ToolResult(success=False, error="path is required")

    try:
        resolved = resolve_inside_workspace(workspace, path_value)
    except (FileNotFoundError, NotADirectoryError, PermissionError) as exc:
        return ToolResult(success=False, error=str(exc), metadata={"path": path_value})

    if not resolved.exists():
        return ToolResult(success=False, error=f"file not found: {path_value}", metadata={"path": path_value})
    if not resolved.is_file():
        return ToolResult(success=False, error=f"path is not a file: {path_value}", metadata={"path": path_value})

    try:
        content = resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ToolResult(success=False, error=f"file is not valid utf-8: {path_value}", metadata={"path": path_value})

    root = ensure_workspace(workspace)
    return ToolResult(
        success=True,
        content=content,
        metadata={
            "path": str(resolved.relative_to(root)),
            "bytes": resolved.stat().st_size,
        },
    )
