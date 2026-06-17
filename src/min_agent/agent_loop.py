from __future__ import annotations

import time

from min_agent.context_builder import ContextBuilder
from min_agent.tool_registry import ToolRegistry
from min_agent.trace_recorder import TraceRecorder
from min_agent.types import AgentRunResult, Observation


class AgentLoop:
    def __init__(
        self,
        context_builder: ContextBuilder,
        llm: object,
        tools: ToolRegistry,
        recorder: TraceRecorder,
        workspace: str,
        max_turns: int = 8,
        step_delay_seconds: float = 0.4,
    ) -> None:
        self.context_builder = context_builder
        self.llm = llm
        self.tools = tools
        self.recorder = recorder
        self.workspace = workspace
        self.max_turns = max_turns
        self.step_delay_seconds = step_delay_seconds
        self.observations: list[Observation] = []

    def run(self, user_goal: str) -> AgentRunResult:
        self.recorder.emit(
            phase="run_started",
            status="running",
            title="收到任务",
            reason="用户提交了一个目标",
            input={"user_goal": user_goal, "workspace": self.workspace},
        )

        for _turn in range(self.max_turns):
            self._pause()
            context = self.context_builder.build(
                user_goal=user_goal,
                workspace=self.workspace,
                available_tools=self.tools.list_specs(),
                observations=self.observations,
            )
            self.recorder.emit(
                phase="context_built",
                status="running",
                title="整理上下文",
                reason="准备用户目标、可用工具和已有观察结果",
                output=context.to_dict(),
            )

            self._pause()
            action = self.llm.decide(context)
            self.recorder.emit(
                phase="llm_decision",
                status="running",
                title="决定下一步",
                reason=action.reason,
                output=action.to_dict(),
            )

            if action.kind == "final_answer":
                message = action.message or ""
                status = "completed" if action.success else "failed"
                self.recorder.emit(
                    phase="final_answer",
                    status=status,
                    title="生成最终回答",
                    reason=action.reason,
                    output={"message": message},
                )
                self.recorder.emit(
                    phase="run_completed" if status == "completed" else "run_failed",
                    status=status,
                    title="任务完成" if status == "completed" else "任务失败",
                    output={"message": message},
                )
                return AgentRunResult(message=message, success=action.success)

            if action.tool_name is None:
                return self._fail("模型返回了工具调用，但没有提供工具名称")

            self._pause()
            self.recorder.emit(
                phase="tool_started",
                status="running",
                title=f"调用工具：{action.tool_name}",
                reason=action.reason,
                input={"tool_name": action.tool_name, "args": action.args},
            )

            result = self.tools.call(action.tool_name, action.args)
            event_status = "completed" if result.success else "failed"
            self.recorder.emit(
                phase="tool_finished",
                status=event_status,
                title=f"工具返回：{action.tool_name}",
                reason="工具执行完成" if result.success else "工具执行失败",
                output=result.to_dict(),
            )

            observation = Observation(tool_name=action.tool_name, args=action.args, result=result)
            self.observations.append(observation)
            self.recorder.emit(
                phase="observation_added",
                status="running",
                title="吸收工具结果",
                reason="把工具结果写回上下文，供下一轮判断使用",
                output=observation.to_dict(),
            )

        return self._fail("达到最大轮次限制，Agent 停止以避免无限循环")

    def _fail(self, message: str) -> AgentRunResult:
        self.recorder.emit(
            phase="run_failed",
            status="failed",
            title="任务失败",
            reason=message,
            output={"message": message},
        )
        return AgentRunResult(message=message, success=False)

    def _pause(self) -> None:
        if self.step_delay_seconds > 0:
            time.sleep(self.step_delay_seconds)
