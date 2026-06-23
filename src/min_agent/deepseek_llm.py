from __future__ import annotations

import json
from typing import Protocol

from min_agent.deepseek_client import ModelClientError
from min_agent.types import AgentAction, AgentContext


class ChatCompletionClient(Protocol):
    def create_chat_completion(self, system_prompt: str, user_prompt: str) -> str:
        ...


class DeepSeekLLM:
    def __init__(self, client: ChatCompletionClient, model: str) -> None:
        self.client = client
        self.model = model

    def decide(self, context: AgentContext) -> AgentAction:
        system_prompt = self._system_prompt()
        user_prompt = self._user_prompt(context)
        try:
            raw_content = self.client.create_chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        except ModelClientError as exc:
            return AgentAction.final_answer(
                message=f"模型调用失败：{exc}",
                reason="DeepSeek 请求失败",
                success=False,
                metadata=self._model_call_metadata(system_prompt, user_prompt, error=str(exc)),
            )

        metadata = self._model_call_metadata(system_prompt, user_prompt, raw_content=raw_content)
        try:
            data = json.loads(raw_content)
        except json.JSONDecodeError:
            return self._invalid_action(
                "模型返回了无法解析的决策 JSON。",
                "模型输出不是合法 JSON",
                metadata=metadata,
            )

        return self._action_from_data(data, context, metadata)

    def _action_from_data(
        self,
        data: object,
        context: AgentContext,
        metadata: dict[str, object],
    ) -> AgentAction:
        if not isinstance(data, dict):
            return self._invalid_action("模型返回了无法解析的决策 JSON。", "模型输出不是 JSON object", metadata)

        kind = data.get("kind")
        reason = data.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            reason = "模型没有提供有效 reason"

        if kind == "tool_call":
            tool_name = data.get("tool_name")
            args = data.get("args")
            if not isinstance(tool_name, str) or not tool_name:
                return self._invalid_action("模型返回的工具调用缺少 tool_name。", reason, metadata)
            if tool_name not in {tool.name for tool in context.available_tools}:
                return self._invalid_action(f"模型请求了不可用工具：{tool_name}", reason, metadata)
            if not isinstance(args, dict):
                return self._invalid_action("模型返回的工具调用缺少 args。", reason, metadata)
            return AgentAction.tool_call(tool_name=tool_name, args=args, reason=reason, metadata=metadata)

        if kind == "final_answer":
            message = data.get("message")
            success = data.get("success", True)
            if not isinstance(message, str):
                return self._invalid_action("模型返回的最终回答缺少 message。", reason, metadata)
            if not isinstance(success, bool):
                return self._invalid_action("模型返回的 success 不是布尔值。", reason, metadata)
            return AgentAction.final_answer(message=message, reason=reason, success=success, metadata=metadata)

        return self._invalid_action("模型返回了未知的决策类型。", reason, metadata)

    def _invalid_action(
        self,
        message: str,
        reason: str,
        metadata: dict[str, object] | None = None,
    ) -> AgentAction:
        return AgentAction.final_answer(message=message, reason=reason, success=False, metadata=metadata or {})

    def _model_call_metadata(
        self,
        system_prompt: str,
        user_prompt: str,
        raw_content: str | None = None,
        error: str | None = None,
    ) -> dict[str, object]:
        response: dict[str, str] = {}
        if raw_content is not None:
            response["content"] = raw_content
        if error is not None:
            response["error"] = error
        return {
            "model_call": {
                "provider": "deepseek",
                "model": self.model,
                "request": {
                    "system_prompt": system_prompt,
                    "user_prompt": user_prompt,
                },
                "response": response,
            }
        }

    def _system_prompt(self) -> str:
        return """You are the decision model for min-agent-demo.
Return only one valid json object matching the local AgentAction schema.
Do not use markdown fences.
Do not invent tools.
Only choose tools listed in the user prompt.
Use list_dir when you need to inspect available workspace files.
Use read_file when you need file content before answering.

Allowed json outputs:
{
  "kind": "tool_call",
  "tool_name": "list_dir",
  "args": {"path": "."},
  "reason": "Need to inspect available workspace files"
}

{
  "kind": "tool_call",
  "tool_name": "read_file",
  "args": {"path": "notes.md"},
  "reason": "Need file content before answering"
}

{
  "kind": "final_answer",
  "message": "Final answer text",
  "reason": "Enough information is available",
  "success": true
}
"""

    def _user_prompt(self, context: AgentContext) -> str:
        return json.dumps(
            {
                "model": self.model,
                "user_goal": context.user_goal,
                "workspace": context.workspace,
                "available_tools": [tool.to_dict() for tool in context.available_tools],
                "observations": [observation.to_dict() for observation in context.observations],
            },
            ensure_ascii=False,
            indent=2,
        )
