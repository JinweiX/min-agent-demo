from __future__ import annotations

import re

from min_agent.types import AgentAction, AgentContext, Observation


FILE_PATTERN = re.compile(r"[\w./-]+\.md")
MAX_FAKE_READS = 3
PATH_KEYWORDS = {
    "architecture": ("architecture", "架构", "结构", "模块", "流程"),
    "notes": ("notes", "笔记", "示例"),
    "project": ("project", "项目", "demo", "目标", "概览"),
    "usage": ("usage", "使用", "方式", "用法", "运行", "命令"),
}


class FakeLLM:
    def decide(self, context: AgentContext) -> AgentAction:
        target_paths = self._extract_target_paths(context.user_goal)[:MAX_FAKE_READS]
        if not target_paths:
            listing_observation = self._find_latest_observation(
                context.observations,
                "list_dir",
                {"path": "."},
            )
            if listing_observation is None:
                if self._tool_available(context, "list_dir"):
                    return AgentAction.tool_call(
                        tool_name="list_dir",
                        args={"path": "."},
                        reason="用户目标没有指定 Markdown 文件，需要先查看 workspace 根目录中有哪些文件",
                    )
                return self._cannot_decide_without_file_path()

            if not listing_observation.result.success:
                return AgentAction.final_answer(
                    message=f"列出 workspace 文件失败：{listing_observation.result.error}",
                    reason="目录列表工具没有返回可用于选择文件的结果",
                    success=False,
                )

            target_paths = self._select_markdown_paths(
                context.user_goal,
                self._markdown_paths_from_listing(listing_observation),
            )[:MAX_FAKE_READS]
            if not target_paths:
                return AgentAction.final_answer(
                    message="没有在 workspace 根目录中发现可总结的 Markdown 文件。",
                    reason="目录列表结果中没有 type=file 且 path 以 .md 结尾的条目",
                    success=False,
                )

        for target_path in target_paths:
            observation = self._find_latest_read_observation(context.observations, target_path)
            if observation is None:
                if not self._tool_available(context, "read_file"):
                    return AgentAction.final_answer(
                        message=f"无法读取 {target_path}：当前上下文没有可用的 read_file 工具。",
                        reason="计划读取 Markdown 文件，但 read_file 工具不可用",
                        success=False,
                    )
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
            message=self._preview_multiple_files(target_paths, context.observations),
            reason="已经获得计划内 Markdown 文件内容，可以基于 observation 生成总结",
        )

    def _cannot_decide_without_file_path(self) -> AgentAction:
        return AgentAction.final_answer(
            message="无法判断需要读取哪个文件。请在任务中提供明确的 .md 文件名。",
            reason="用户目标中没有可识别的 Markdown 文件路径，且无法列出 workspace 文件",
            success=False,
        )

    def _extract_target_paths(self, user_goal: str) -> list[str]:
        target_paths: list[str] = []
        for match in FILE_PATTERN.findall(user_goal):
            if match not in target_paths:
                target_paths.append(match)
        return target_paths

    def _tool_available(self, context: AgentContext, tool_name: str) -> bool:
        return any(tool.name == tool_name for tool in context.available_tools)

    def _find_latest_observation(
        self,
        observations: list[Observation],
        tool_name: str,
        args: dict[str, object],
    ) -> Observation | None:
        for observation in reversed(observations):
            if observation.tool_name == tool_name and observation.args == args:
                return observation
        return None

    def _markdown_paths_from_listing(self, observation: Observation) -> list[str]:
        entries = observation.result.metadata.get("entries")
        if not isinstance(entries, list):
            return []

        target_paths: list[str] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            path = entry.get("path")
            if entry.get("type") != "file" or not isinstance(path, str) or not path.endswith(".md"):
                continue
            if path not in target_paths:
                target_paths.append(path)
        return target_paths

    def _select_markdown_paths(self, user_goal: str, paths: list[str]) -> list[str]:
        scored_paths = [
            (self._path_relevance_score(user_goal, path), index, path)
            for index, path in enumerate(paths)
        ]
        scored_paths.sort(key=lambda item: (-item[0], item[1]))
        return [path for _score, _index, path in scored_paths]

    def _path_relevance_score(self, user_goal: str, path: str) -> int:
        normalized_goal = user_goal.lower()
        normalized_path = path.lower()
        score = 0
        for path_keyword, goal_keywords in PATH_KEYWORDS.items():
            if path_keyword not in normalized_path:
                continue
            for keyword in goal_keywords:
                if keyword.lower() in normalized_goal:
                    score += 1
        return score

    def _find_latest_read_observation(
        self,
        observations: list[Observation],
        target_path: str,
    ) -> Observation | None:
        observation = self._find_latest_observation(
            observations,
            "read_file",
            {"path": target_path},
        )
        return observation

    def _preview_multiple_files(self, target_paths: list[str], observations: list[Observation]) -> str:
        previews: list[str] = []
        for target_path in target_paths:
            observation = self._find_latest_read_observation(observations, target_path)
            content = observation.result.content if observation else ""
            previews.append(self._preview_content(target_path, content))
        return "\n".join(previews)

    def _preview_content(self, target_path: str, content: str) -> str:
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if not lines:
            return f"{target_path} 是一个空文件，没有可总结的内容。"
        preview = "；".join(lines[:3])
        return f"{target_path} 的主要内容：{preview}"
