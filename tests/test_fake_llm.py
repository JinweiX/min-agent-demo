from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class FakeLLMTest(unittest.TestCase):
    def test_decides_to_read_target_file_when_content_missing(self) -> None:
        from min_agent.fake_llm import FakeLLM
        from min_agent.types import AgentContext, ToolSpec

        llm = FakeLLM()
        context = AgentContext(
            user_goal="请读取 notes.md 并总结",
            workspace="examples/workspace",
            available_tools=[ToolSpec(name="read_file", description="Read file")],
            observations=[],
        )

        action = llm.decide(context)

        self.assertEqual(action.kind, "tool_call")
        self.assertEqual(action.tool_name, "read_file")
        self.assertEqual(action.args, {"path": "notes.md"})
        self.assertIn("还没有", action.reason)

    def test_final_answer_after_successful_read(self) -> None:
        from min_agent.fake_llm import FakeLLM
        from min_agent.types import AgentContext, Observation, ToolResult, ToolSpec

        llm = FakeLLM()
        context = AgentContext(
            user_goal="请读取 notes.md 并总结",
            workspace="examples/workspace",
            available_tools=[ToolSpec(name="read_file", description="Read file")],
            observations=[
                Observation(
                    tool_name="read_file",
                    args={"path": "notes.md"},
                    result=ToolResult(success=True, content="# 示例笔记\n这是一个 Agent demo。"),
                )
            ],
        )

        action = llm.decide(context)

        self.assertEqual(action.kind, "final_answer")
        self.assertIn("示例笔记", action.message or "")

    def test_final_answer_after_failed_read(self) -> None:
        from min_agent.fake_llm import FakeLLM
        from min_agent.types import AgentContext, Observation, ToolResult, ToolSpec

        llm = FakeLLM()
        context = AgentContext(
            user_goal="请读取 missing.md 并总结",
            workspace="examples/workspace",
            available_tools=[ToolSpec(name="read_file", description="Read file")],
            observations=[
                Observation(
                    tool_name="read_file",
                    args={"path": "missing.md"},
                    result=ToolResult(success=False, error="file not found: missing.md"),
                )
            ],
        )

        action = llm.decide(context)

        self.assertEqual(action.kind, "final_answer")
        self.assertFalse(action.success)
        self.assertIn("读取文件失败", action.message or "")

    def test_lists_workspace_when_no_file_path_is_named(self) -> None:
        from min_agent.fake_llm import FakeLLM
        from min_agent.types import AgentContext, ToolSpec

        llm = FakeLLM()
        context = AgentContext(
            user_goal="请总结一下",
            workspace="examples/workspace",
            available_tools=[
                ToolSpec(name="list_dir", description="List directory"),
                ToolSpec(name="read_file", description="Read file"),
            ],
            observations=[],
        )

        action = llm.decide(context)

        self.assertEqual(action.kind, "tool_call")
        self.assertEqual(action.tool_name, "list_dir")
        self.assertEqual(action.args, {"path": "."})

    def test_cannot_decide_without_file_path_when_list_dir_unavailable(self) -> None:
        from min_agent.fake_llm import FakeLLM
        from min_agent.types import AgentContext, ToolSpec

        llm = FakeLLM()
        context = AgentContext(
            user_goal="请总结一下",
            workspace="examples/workspace",
            available_tools=[ToolSpec(name="read_file", description="Read file")],
            observations=[],
        )

        action = llm.decide(context)

        self.assertEqual(action.kind, "final_answer")
        self.assertFalse(action.success)
        self.assertIn("无法判断", action.message or "")

    def test_reads_markdown_file_after_successful_listing(self) -> None:
        from min_agent.fake_llm import FakeLLM
        from min_agent.types import AgentContext, Observation, ToolResult, ToolSpec

        llm = FakeLLM()
        context = AgentContext(
            user_goal="请总结一下",
            workspace="examples/workspace",
            available_tools=[
                ToolSpec(name="list_dir", description="List directory"),
                ToolSpec(name="read_file", description="Read file"),
            ],
            observations=[
                Observation(
                    tool_name="list_dir",
                    args={"path": "."},
                    result=ToolResult(
                        success=True,
                        metadata={
                            "entries": [
                                {"type": "file", "path": "architecture.md"},
                                {"type": "file", "path": "notes.md"},
                                {"type": "directory", "path": "docs"},
                            ]
                        },
                    ),
                )
            ],
        )

        action = llm.decide(context)

        self.assertEqual(action.kind, "tool_call")
        self.assertEqual(action.tool_name, "read_file")
        self.assertEqual(action.args, {"path": "architecture.md"})

    def test_prefers_relevant_markdown_file_after_successful_listing(self) -> None:
        from min_agent.fake_llm import FakeLLM
        from min_agent.types import AgentContext, Observation, ToolResult, ToolSpec

        llm = FakeLLM()
        context = AgentContext(
            user_goal="请总结这个 demo 的使用方式",
            workspace="examples/workspace",
            available_tools=[
                ToolSpec(name="list_dir", description="List directory"),
                ToolSpec(name="read_file", description="Read file"),
            ],
            observations=[
                Observation(
                    tool_name="list_dir",
                    args={"path": "."},
                    result=ToolResult(
                        success=True,
                        metadata={
                            "entries": [
                                {"type": "file", "path": "architecture.md"},
                                {"type": "file", "path": "notes.md"},
                                {"type": "file", "path": "project.md"},
                                {"type": "file", "path": "usage.md"},
                            ]
                        },
                    ),
                )
            ],
        )

        action = llm.decide(context)

        self.assertEqual(action.kind, "tool_call")
        self.assertEqual(action.tool_name, "read_file")
        self.assertEqual(action.args, {"path": "usage.md"})

    def test_final_answer_after_multiple_successful_reads(self) -> None:
        from min_agent.fake_llm import FakeLLM
        from min_agent.types import AgentContext, Observation, ToolResult, ToolSpec

        llm = FakeLLM()
        context = AgentContext(
            user_goal="请总结一下",
            workspace="examples/workspace",
            available_tools=[
                ToolSpec(name="list_dir", description="List directory"),
                ToolSpec(name="read_file", description="Read file"),
            ],
            observations=[
                Observation(
                    tool_name="list_dir",
                    args={"path": "."},
                    result=ToolResult(
                        success=True,
                        metadata={
                            "entries": [
                                {"type": "file", "path": "architecture.md"},
                                {"type": "file", "path": "project.md"},
                            ]
                        },
                    ),
                ),
                Observation(
                    tool_name="read_file",
                    args={"path": "architecture.md"},
                    result=ToolResult(success=True, content="# 架构\nAgent Loop。"),
                ),
                Observation(
                    tool_name="read_file",
                    args={"path": "project.md"},
                    result=ToolResult(success=True, content="# 项目\n最小演示。"),
                ),
            ],
        )

        action = llm.decide(context)

        self.assertEqual(action.kind, "final_answer")
        self.assertIn("architecture.md", action.message or "")
        self.assertIn("project.md", action.message or "")

    def test_explicit_markdown_paths_are_capped_before_final_answer(self) -> None:
        from min_agent.fake_llm import FakeLLM, MAX_FAKE_READS
        from min_agent.types import AgentContext, Observation, ToolResult, ToolSpec

        llm = FakeLLM()
        named_paths = ["a.md", "b.md", "c.md", "d.md"]
        context = AgentContext(
            user_goal=f"请总结 {' '.join(named_paths)}",
            workspace="examples/workspace",
            available_tools=[ToolSpec(name="read_file", description="Read file")],
            observations=[
                Observation(
                    tool_name="read_file",
                    args={"path": target_path},
                    result=ToolResult(success=True, content=f"# {target_path}\n内容"),
                )
                for target_path in named_paths[:MAX_FAKE_READS]
            ],
        )

        action = llm.decide(context)

        self.assertEqual(action.kind, "final_answer")
        for target_path in named_paths[:MAX_FAKE_READS]:
            self.assertIn(target_path, action.message or "")
        self.assertNotIn(named_paths[MAX_FAKE_READS], action.message or "")

    def test_fails_when_read_file_unavailable_after_listing(self) -> None:
        from min_agent.fake_llm import FakeLLM
        from min_agent.types import AgentContext, Observation, ToolResult, ToolSpec

        llm = FakeLLM()
        context = AgentContext(
            user_goal="请总结一下",
            workspace="examples/workspace",
            available_tools=[ToolSpec(name="list_dir", description="List directory")],
            observations=[
                Observation(
                    tool_name="list_dir",
                    args={"path": "."},
                    result=ToolResult(
                        success=True,
                        metadata={"entries": [{"type": "file", "path": "notes.md"}]},
                    ),
                )
            ],
        )

        action = llm.decide(context)

        self.assertEqual(action.kind, "final_answer")
        self.assertFalse(action.success)
        self.assertIsNone(action.tool_name)


if __name__ == "__main__":
    unittest.main()
