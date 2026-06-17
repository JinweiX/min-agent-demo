from __future__ import annotations

import re

from min_agent.types import AgentAction, AgentContext, Observation


FILE_PATTERN = re.compile(r"[\w./-]+\.md")


class FakeLLM:
    def decide(self, context: AgentContext) -> AgentAction:
        target_path = self._extract_target_path(context.user_goal)
        if target_path is None:
            return AgentAction.final_answer(
                message="无法判断需要读取哪个文件。请在任务中提供明确的 .md 文件名。",
                reason="用户目标中没有可识别的 Markdown 文件路径",
                success=False,
            )

        observation = self._find_latest_read_observation(context.observations, target_path)
        if observation is None:
            return AgentAction.tool_call(
                tool_name="read_file",
                args={"path": target_path},
                reason=f"还没有 {target_path} 的内容，需要先读取文件后才能总结",
            )

        if not observation.result.success:
            return AgentAction.final_answer(
                message=f"读取文件失败：{observation.result.error}",
                reason="工具没有返回可用于总结的文件内容",
                success=False,
            )

        return AgentAction.final_answer(
            message=self._preview_content(target_path, observation.result.content),
            reason="已经获得文件内容，可以基于 observation 生成总结",
        )

    def _extract_target_path(self, user_goal: str) -> str | None:
        match = FILE_PATTERN.search(user_goal)
        return match.group(0) if match else None

    def _find_latest_read_observation(
        self,
        observations: list[Observation],
        target_path: str,
    ) -> Observation | None:
        for observation in reversed(observations):
            if observation.tool_name == "read_file" and observation.args.get("path") == target_path:
                return observation
        return None

    def _preview_content(self, target_path: str, content: str) -> str:
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if not lines:
            return f"{target_path} 是一个空文件，没有可总结的内容。"
        preview = "；".join(lines[:3])
        return f"{target_path} 的主要内容：{preview}"
