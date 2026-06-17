# min-agent-demo 项目规则

## 项目目标

本项目用于实现一个可观察的最小 Agent 机制 demo。

第一版不是生产工具，也不是迷你 Claude Code。第一版只验证：

```text
目标输入 -> 判断下一步 -> 调用工具 -> 获得结果 -> 更新判断 -> 输出答案
```

核心体验是：用户输入一个简单任务后，可以在浏览器观察窗口中实时看到 Agent 执行到了哪一步，以及每一步为什么发生。

## 第一版边界

第一版只做：

- CLI 启动入口
- 示例 workspace
- FakeLLM 决策器
- Agent Loop 骨架
- Tool Registry
- 读取文件工具
- Trace Recorder
- Trace Server
- Trace Viewer
- 运行记录保存
- 最小测试

第一版不做：

- 真实大模型接入
- 写文件
- 运行命令
- 页面控制 Agent
- 暂停、继续、打断
- 多 Agent
- 长期记忆
- MCP、Hook、插件系统
- 复杂前端工作台

## 架构红线

这些规则用于防止第一版退化成写死的流程演示。

1. `AgentLoop` 不能写死 `notes.md`，也不能写死固定 7 步流程。
2. `FakeLLM` 必须根据当前上下文和 observation 判断下一步，不能靠 step number 推进。
3. `FakeLLM` 是可替换的决策器，后续真实模型应能替换它。
4. 工具必须通过 `ToolRegistry` 注册和调用，不能在 `AgentLoop` 中直接调用具体工具实现。
5. 上下文必须通过 observation 累积变化，不能通过全局变量或固定脚本推进。
6. Trace Viewer 只展示事件，不控制 Agent。
7. 实时观察窗口展示的是运行事件，不是预设流程动画。
8. 文件工具只能访问指定 workspace 内的文件。
9. 写文件、运行命令等危险动作后续必须走权限确认。
10. 真实模型、API key、`.env` 相关内容不得进入第一版实现。

## 目录约定

```text
min-agent-demo/
  AGENTS.md
  README.md
  pyproject.toml
  src/
    min_agent/
      __init__.py
      cli.py
      agent_loop.py
      context_builder.py
      fake_llm.py
      tool_registry.py
      trace_recorder.py
      trace_server.py
      types.py
      tools/
        __init__.py
        workspace.py
  web/
    trace_viewer.html
    trace_viewer.js
    trace_viewer.css
  examples/
    workspace/
      notes.md
  runs/
    .gitkeep
  docs/
    runbook.md
  tests/
    test_project_structure.py
```

当前初始化阶段可以先创建最小占位文件。后续实现时再补齐具体模块。

## Workspace 边界

默认 workspace：

```text
examples/workspace/
```

后续 CLI 应支持：

```text
--workspace examples/workspace
```

文件工具规则：

- 用户传入相对路径时，相对 workspace 解析。
- 拒绝 `..` 逃逸路径。
- 拒绝 workspace 外绝对路径。
- 文件不存在时返回工具错误，不让程序崩溃。

## Trace 和运行记录

Trace 事件必须是结构化数据，而不是只能给人看的字符串。

运行记录建议保存为：

```text
runs/YYYYMMDD-HHMMSS-<run-id>.json
```

每条事件至少包含：

- step
- timestamp
- phase
- status
- title
- reason
- input
- output

实时推送和本地保存应尽量复用同一套事件结构。

## 前端约定

Trace Viewer 是只读观察窗口。

`trace_viewer.js` 即使不拆成多个文件，也要在代码结构上分清三类职责：

- 连接管理：连接 SSE、处理断开和重连
- 状态维护：保存事件列表、当前步骤和运行状态
- 页面渲染：根据状态更新时间线和详情区域

第一版不引入前端框架。

## 技术约定

- Python 最低版本：3.10+
- 第一版优先使用标准库
- 不安装新全局依赖
- 不读取真实 API key
- 不创建 `.env`
- 不接真实模型 SDK

## 验证命令

每次修改后至少运行：

```bash
python3 -m unittest discover -s tests
```

后续如果引入安装步骤、统一 `python` 命令或改用 `pytest`，必须先更新本文件和 README。

## 开发流程

1. 新增或修改文件前，先说明计划并取得确认。
2. 大改动前先更新方案或规则，再改实现。
3. 实现时保持小步提交粒度，但未经确认不执行 git commit。
4. 不执行 git push、rebase、reset、强推等操作，除非用户明确要求。
5. 发现方案和实现冲突时，先修正文档或规则，再继续实现。
