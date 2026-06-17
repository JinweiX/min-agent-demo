# min-agent-demo

一个可观察的最小 Agent 机制 demo。

第一版目标不是做一个可用于生产的 Agent，而是用最小场景看清楚 Agent 的核心闭环：

```text
目标输入 -> 判断下一步 -> 调用工具 -> 获得结果 -> 更新判断 -> 输出答案
```

## 第一版目标

用户输入一个简单任务：

```text
请读取示例工作区里的 notes.md，并总结内容
```

系统应该逐步展示：

1. 收到任务
2. 整理上下文
3. 判断需要读取文件
4. 调用文件读取工具
5. 获得文件内容
6. 基于文件内容生成总结
7. 完成任务

这些步骤不能被写死成流程动画。后续实现必须由 Agent Loop、FakeLLM、Tool Registry、Observation 和 Trace 事件共同推进。

## 当前状态

当前仓库处于初始化阶段，只包含项目规则、目录骨架和最小占位入口。

完整实现顺序见：

- `最小 Agent Demo 技术方案规划.md`
- `AGENTS.md`

## 运行占位 CLI

当前 CLI 只是项目初始化占位，用于确认包结构可运行：

```bash
PYTHONPATH=src python3 -m min_agent.cli "请读取 notes.md 并总结" --workspace examples/workspace
```

## 运行测试

```bash
python3 -m unittest discover -s tests
```

## 关键原则

- 第一版用 FakeLLM，不接真实模型。
- FakeLLM 必须按上下文和 observation 决策。
- Agent Loop 不能写死 `notes.md` 或固定 7 步。
- 工具必须通过 Tool Registry 调用。
- Trace Viewer 只展示事件，不控制 Agent。
- 文件工具只能访问 workspace 内文件。
