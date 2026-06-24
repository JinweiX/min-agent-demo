from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Union


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class StubClient:
    def __init__(self, content: Union[str, Exception]) -> None:
        self.content = content
        self.calls = []

    def create_chat_completion(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        if isinstance(self.content, Exception):
            raise self.content
        return self.content


class DeepSeekLLMTest(unittest.TestCase):
    def test_parses_tool_call(self) -> None:
        from min_agent.deepseek_llm import DeepSeekLLM
        from min_agent.types import AgentContext, ToolSpec

        llm = DeepSeekLLM(
            client=StubClient(
                '{"kind":"tool_call","tool_name":"read_file","args":{"path":"notes.md"},"reason":"需要读取文件"}'
            ),
            model="deepseek-v4-flash",
        )
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

    def test_parses_final_answer(self) -> None:
        from min_agent.deepseek_llm import DeepSeekLLM
        from min_agent.types import AgentContext, ToolSpec

        llm = DeepSeekLLM(
            client=StubClient('{"kind":"final_answer","message":"总结完成","reason":"已有内容","success":true}'),
            model="deepseek-v4-flash",
        )
        context = AgentContext(
            user_goal="请读取 notes.md 并总结",
            workspace="examples/workspace",
            available_tools=[ToolSpec(name="read_file", description="Read file")],
            observations=[],
        )

        action = llm.decide(context)

        self.assertEqual(action.kind, "final_answer")
        self.assertTrue(action.success)
        self.assertEqual(action.message, "总结完成")

    def test_invalid_json_becomes_failed_final_answer(self) -> None:
        from min_agent.deepseek_llm import DeepSeekLLM
        from min_agent.types import AgentContext, ToolSpec

        llm = DeepSeekLLM(client=StubClient("not json"), model="deepseek-v4-flash")
        context = AgentContext(
            user_goal="请读取 notes.md 并总结",
            workspace="examples/workspace",
            available_tools=[ToolSpec(name="read_file", description="Read file")],
            observations=[],
        )

        action = llm.decide(context)

        self.assertEqual(action.kind, "final_answer")
        self.assertFalse(action.success)
        self.assertIn("无法解析", action.message or "")

    def test_unknown_tool_becomes_failed_final_answer(self) -> None:
        from min_agent.deepseek_llm import DeepSeekLLM
        from min_agent.types import AgentContext, ToolSpec

        llm = DeepSeekLLM(
            client=StubClient(
                '{"kind":"tool_call","tool_name":"delete_file","args":{"path":"notes.md"},"reason":"错误工具"}'
            ),
            model="deepseek-v4-flash",
        )
        context = AgentContext(
            user_goal="请读取 notes.md 并总结",
            workspace="examples/workspace",
            available_tools=[ToolSpec(name="read_file", description="Read file")],
            observations=[],
        )

        action = llm.decide(context)

        self.assertEqual(action.kind, "final_answer")
        self.assertFalse(action.success)
        self.assertIn("不可用工具", action.message or "")

    def test_client_error_becomes_failed_final_answer(self) -> None:
        from min_agent.deepseek_client import ModelClientError
        from min_agent.deepseek_llm import DeepSeekLLM
        from min_agent.types import AgentContext, ToolSpec

        llm = DeepSeekLLM(
            client=StubClient(ModelClientError("DeepSeek request failed with HTTP 500")),
            model="deepseek-v4-flash",
        )
        context = AgentContext(
            user_goal="请读取 notes.md 并总结",
            workspace="examples/workspace",
            available_tools=[ToolSpec(name="read_file", description="Read file")],
            observations=[],
        )

        action = llm.decide(context)

        self.assertEqual(action.kind, "final_answer")
        self.assertFalse(action.success)
        self.assertIn("模型调用失败", action.message or "")

    def test_prompt_mentions_json_and_action_schema(self) -> None:
        from min_agent.deepseek_llm import DeepSeekLLM
        from min_agent.types import AgentContext, ToolSpec

        client = StubClient('{"kind":"final_answer","message":"ok","reason":"done","success":true}')
        llm = DeepSeekLLM(client=client, model="deepseek-v4-flash")
        context = AgentContext(
            user_goal="请读取 notes.md 并总结",
            workspace="examples/workspace",
            available_tools=[ToolSpec(name="read_file", description="Read file")],
            observations=[],
        )

        llm.decide(context)

        system_prompt, user_prompt = client.calls[0]
        self.assertIn("json", system_prompt.lower())
        self.assertIn("AgentAction", system_prompt)
        self.assertIn("available_tools", user_prompt)

    def test_system_prompt_allows_list_dir_tool(self) -> None:
        from min_agent.deepseek_llm import DeepSeekLLM

        llm = DeepSeekLLM(
            client=StubClient('{"kind":"final_answer","message":"ok","reason":"done","success":true}'),
            model="deepseek-v4-flash",
        )

        system_prompt = llm._system_prompt()

        self.assertIn('"tool_name": "list_dir"', system_prompt)
        self.assertIn('"args": {"path": "."}', system_prompt)
        self.assertIn('"tool_name": "read_file"', system_prompt)

    def test_action_metadata_contains_model_call_request_and_raw_content(self) -> None:
        from min_agent.deepseek_llm import DeepSeekLLM
        from min_agent.types import AgentContext, ToolSpec

        raw_content = '{"kind":"tool_call","tool_name":"read_file","args":{"path":"notes.md"},"reason":"需要读取文件"}'
        llm = DeepSeekLLM(client=StubClient(raw_content), model="deepseek-v4-flash")
        context = AgentContext(
            user_goal="请读取 notes.md 并总结",
            workspace="examples/workspace",
            available_tools=[ToolSpec(name="read_file", description="Read file")],
            observations=[],
        )

        action = llm.decide(context)

        model_call = action.metadata["model_call"]
        self.assertEqual(model_call["provider"], "deepseek")
        self.assertEqual(model_call["model"], "deepseek-v4-flash")
        self.assertIn("AgentAction", model_call["request"]["system_prompt"])
        self.assertIn("available_tools", model_call["request"]["user_prompt"])
        self.assertEqual(model_call["response"]["content"], raw_content)


    def test_system_prompt_includes_write_file(self) -> None:
        from min_agent.deepseek_llm import DeepSeekLLM

        llm = DeepSeekLLM(
            client=StubClient('{"kind":"final_answer","message":"ok","reason":"done","success":true}'),
            model="deepseek-v4-flash",
        )

        system_prompt = llm._system_prompt()

        self.assertIn('"tool_name": "write_file"', system_prompt)
        self.assertIn('"mode": "create"', system_prompt)

    def test_system_prompt_says_model_only_proposes_action(self) -> None:
        from min_agent.deepseek_llm import DeepSeekLLM

        llm = DeepSeekLLM(
            client=StubClient('{"kind":"final_answer","message":"ok","reason":"done","success":true}'),
            model="deepseek-v4-flash",
        )

        system_prompt = llm._system_prompt()

        self.assertIn("only propose", system_prompt.lower())

    def test_parses_write_file_action(self) -> None:
        from min_agent.deepseek_llm import DeepSeekLLM
        from min_agent.types import AgentContext, ToolSpec

        llm = DeepSeekLLM(
            client=StubClient(
                '{"kind":"tool_call","tool_name":"write_file","args":{"path":"summary.md","content":"hello","mode":"create"},"reason":"save summary"}'
            ),
            model="deepseek-v4-flash",
        )
        context = AgentContext(
            user_goal="请生成 summary.md",
            workspace="examples/workspace",
            available_tools=[
                ToolSpec(name="read_file", description="Read file"),
                ToolSpec(name="write_file", description="Write file"),
            ],
            observations=[],
        )

        action = llm.decide(context)

        self.assertEqual(action.kind, "tool_call")
        self.assertEqual(action.tool_name, "write_file")
        self.assertEqual(action.args["path"], "summary.md")
        self.assertEqual(action.args["content"], "hello")

    def test_unknown_write_like_action_rejected(self) -> None:
        from min_agent.deepseek_llm import DeepSeekLLM
        from min_agent.types import AgentContext, ToolSpec

        llm = DeepSeekLLM(
            client=StubClient(
                '{"kind":"tool_call","tool_name":"create_file","args":{"path":"summary.md"},"reason":"create"}'
            ),
            model="deepseek-v4-flash",
        )
        context = AgentContext(
            user_goal="请创建文件",
            workspace="examples/workspace",
            available_tools=[
                ToolSpec(name="read_file", description="Read file"),
                ToolSpec(name="write_file", description="Write file"),
            ],
            observations=[],
        )

        action = llm.decide(context)

        self.assertEqual(action.kind, "final_answer")
        self.assertFalse(action.success)
        self.assertIn("不可用工具", action.message or "")


if __name__ == "__main__":
    unittest.main()
