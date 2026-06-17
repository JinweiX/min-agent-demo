"""CLI placeholder for the minimal agent demo."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="min-agent",
        description="Start the minimal observable agent demo.",
    )
    parser.add_argument("goal", help="User goal for the demo agent.")
    parser.add_argument(
        "--workspace",
        default="examples/workspace",
        help="Workspace directory the demo agent may inspect.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    workspace = Path(args.workspace)
    if not workspace.exists():
        parser.error(f"workspace does not exist: {workspace}")

    print("min-agent demo scaffold is ready.")
    print(f"goal: {args.goal}")
    print(f"workspace: {workspace}")
    print("Next step: implement FakeLLM, AgentLoop, ToolRegistry, and Trace Viewer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

