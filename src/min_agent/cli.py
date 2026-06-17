from __future__ import annotations

import argparse
import time
import webbrowser
from pathlib import Path
from typing import Sequence

from min_agent.agent_loop import AgentLoop
from min_agent.context_builder import ContextBuilder
from min_agent.fake_llm import FakeLLM
from min_agent.tool_registry import ToolRegistry
from min_agent.tools.workspace import ensure_workspace, read_file
from min_agent.trace_recorder import TraceRecorder
from min_agent.trace_server import TraceServer
from min_agent.types import ToolSpec


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="min-agent",
        description="Start the minimal observable agent demo.",
    )
    parser.add_argument("goal", help="User goal for the demo agent.")
    parser.add_argument("--workspace", default="examples/workspace", help="Workspace directory.")
    parser.add_argument("--runs-dir", default="runs", help="Directory for run records.")
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Preferred trace viewer port. Use 0 to let the OS choose a free port.",
    )
    parser.add_argument("--no-browser", action="store_true", help="Print viewer URL without opening a browser.")
    parser.add_argument("--no-viewer", action="store_true", help="Run without starting the trace server.")
    parser.add_argument("--keep-open-seconds", type=float, default=5, help="Keep viewer server alive after completion.")
    parser.add_argument("--step-delay", type=float, default=0.4, help="Delay between visible steps.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        workspace = ensure_workspace(args.workspace)
    except (FileNotFoundError, NotADirectoryError) as exc:
        print(f"Error: {exc}")
        return 2

    recorder = TraceRecorder(user_goal=args.goal, workspace=str(workspace))
    server: TraceServer | None = None

    try:
        if not args.no_viewer:
            try:
                server = TraceServer(
                    recorder=recorder,
                    web_dir=Path(__file__).resolve().parents[2] / "web",
                    preferred_port=args.port,
                )
                server.start()
            except OSError as exc:
                if server is not None:
                    server.close()
                print(f"Error: could not start trace viewer: {exc}")
                return 2
            print(f"Trace viewer: {server.url}")
            if not args.no_browser:
                opened = webbrowser.open(server.url)
                if not opened:
                    print(f"Open this URL manually: {server.url}")
        else:
            print("Trace viewer disabled.")

        registry = ToolRegistry()
        registry.register(
            ToolSpec(
                name="read_file",
                description="Read a UTF-8 text file inside the configured workspace.",
                args_schema={"path": "string"},
            ),
            lambda tool_args: read_file(workspace, tool_args),
        )

        loop = AgentLoop(
            context_builder=ContextBuilder(),
            llm=FakeLLM(),
            tools=registry,
            recorder=recorder,
            workspace=str(workspace),
            step_delay_seconds=args.step_delay,
        )
        result = loop.run(args.goal)
        record_path = recorder.save(args.runs_dir, status="completed" if result.success else "failed")

        print(result.message)
        print(f"Run record: {record_path}")

        if server is not None and args.keep_open_seconds > 0:
            time.sleep(args.keep_open_seconds)
        return 0
    except KeyboardInterrupt:
        recorder.emit(
            phase="run_interrupted",
            status="interrupted",
            title="任务已中断",
            reason="用户通过 Ctrl+C 中断",
        )
        record_path = recorder.save(args.runs_dir, status="interrupted")
        print(f"Interrupted. Run record: {record_path}")
        return 130
    finally:
        if server is not None:
            server.close()


if __name__ == "__main__":
    raise SystemExit(main())
