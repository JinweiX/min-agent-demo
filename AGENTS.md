# min-agent-demo 项目规则

## 项目目标

本项目用于实现一个可观察的最小 Agent 机制 demo。

V0.1 不是生产工具，也不是迷你 Claude Code。V0.1 只验证：

```text
目标输入 -> 判断下一步 -> 调用工具 -> 获得结果 -> 更新判断 -> 输出答案
```

核心体验是：用户输入一个简单任务后，可以在浏览器观察窗口中实时看到 Agent 执行到了哪一步，以及每一步为什么发生。

## V0.1 边界

V0.1 只做：

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

V0.1 不做：

- 真实大模型接入
- 写文件
- 运行命令
- 页面控制 Agent
- 暂停、继续、打断
- 多 Agent
- 长期记忆
- MCP、Hook、插件系统
- 复杂前端工作台

## V0.2 边界

V0.2 在 V0.1 基础上只增加：

- DeepSeek 真实模型决策器
- CLI 在 `fake` 和 `deepseek` 决策器之间切换
- DeepSeek JSON Output 到本地 `AgentAction`

V0.2 仍然不做：

- 写 workspace 文件
- 运行命令
- 页面控制 Agent
- 多工具
- 多 Agent
- 长期记忆
- MCP、Hook、插件系统

## V0.3 边界

V0.3 在 V0.2 基础上只增加：

- `list_dir` 只读目录工具
- Agent 根据目录列表选择相关 Markdown 文件
- 多文件读取和综合回答

V0.3 仍然不做：

- 写 workspace 文件
- 运行命令
- 页面控制 Agent
- 长期记忆
- MCP、Hook、插件系统
- 多 Agent

## V0.4 边界

V0.4 在 V0.3 基础上只改进 Trace Viewer 的可理解性：

- 顶部展示本次任务统计
- 展示用户输入的原始需求
- 将最终结果放在观察窗口之前
- 按 Agentic Loop 轮次组织执行过程
- 每轮内部按原始事件顺序展示步骤
- 每个步骤展示可解释的输入和输出
- 大模型决策步骤展示发送内容、返回内容和解析后的本地 AgentAction

V0.4 仍然不做：

- 页面控制 Agent
- 修改 Agent 执行逻辑
- 修改 TraceEvent 结构
- 写 workspace 文件
- 运行命令
- 长期记忆
- MCP、Hook、插件系统
- 多 Agent

## V0.5 边界

V0.5 在 V0.4 基础上只增加可控写文件权限。这个版本落实架构红线第 9 条：写文件、运行命令等危险动作后续必须走权限确认。

- `write_file` 创建 workspace 内新文本文件
- 写文件前必须 CLI 确认
- Trace Viewer 展示权限申请、用户决策和写入结果

V0.5 仍然不做：

- 覆盖文件
- 运行命令
- 页面控制 Agent
- 网页批准权限
- 写 `.env`
- 长期记忆
- 多 Agent
- MCP、Hook、插件系统

## V0.3 安全规则

- `list_dir` 和 `read_file` 都只能访问指定 workspace 内路径。
- `list_dir` 不递归扫描目录。
- `list_dir` 不暴露 workspace 外 symlink 目标。
- DeepSeek 只能返回 `list_dir`、`read_file` 或 `final_answer` 类型的本地 `AgentAction` JSON。
- 工具执行仍必须通过 `ToolRegistry`。

## V0.2 模型安全规则

- `DEEPSEEK_API_KEY` 只能从环境变量读取。
- 不创建 `.env`。
- 不把 API key 写入代码、日志、TraceEvent 或 run record。
- 默认 `fake` 模式不得读取或校验 `DEEPSEEK_API_KEY`。
- 只有 `--decision-model deepseek` 时才校验 `DEEPSEEK_API_KEY`。
- DeepSeek 模型只能返回本地 `AgentAction` JSON。
- DeepSeek 模型不能直接执行工具。
- 工具执行仍必须通过 `ToolRegistry`。
- 模型请求失败、超时、HTTP 非 2xx、空 content、非法 JSON、非法 action 都必须收敛为可观察的失败结果，不能让 CLI 崩溃。

## 架构红线

这些规则用于防止 V0.1 退化成写死的流程演示。

1. `AgentLoop` 不能写死 `notes.md`，也不能写死固定 7 步流程。
2. `FakeLLM` 必须根据当前上下文和 observation 判断下一步，不能靠 step number 推进。
3. `FakeLLM` 是可替换的决策器，后续真实模型应能替换它。
4. 工具必须通过 `ToolRegistry` 注册和调用，不能在 `AgentLoop` 中直接调用具体工具实现。
5. 上下文必须通过 observation 累积变化，不能通过全局变量或固定脚本推进。
6. Trace Viewer 只展示事件，不控制 Agent。
7. 实时观察窗口展示的是运行事件，不是预设流程动画。
8. 文件工具只能访问指定 workspace 内的文件。
9. 写文件、运行命令等危险动作后续必须走权限确认。
10. 真实模型、API key、`.env` 相关内容不得进入 V0.1 实现。

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
      decision_model.py
      deepseek_client.py
      deepseek_llm.py
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

## 版本记录约定

项目版本变化记录在根目录 `CHANGELOG.md`。

版本记录面向使用者和产品评审者阅读，优先说明：

- 这一版解决什么问题
- 使用者能感受到什么变化
- 这一版不会做什么
- 怎么判断这一版完成

不要把版本记录写成代码提交清单。技术实现细节只保留必要摘要，详细开发计划放在 `docs/superpowers/plans/`。

## 前端约定

Trace Viewer 是只读观察窗口。

`trace_viewer.js` 即使不拆成多个文件，也要在代码结构上分清三类职责：

- 连接管理：连接 SSE、处理断开和重连
- 状态维护：保存事件列表、当前步骤和运行状态
- 页面渲染：根据状态更新时间线和详情区域

V0.1 不引入前端框架。

## 外部执行模型开发指引规则

当 Codex 输出开发计划，并交给 DeepSeek 或其他外部执行模型实现时，计划必须降低“货不对板”的风险。

### 计划必须包含最终效果

开发计划不能只写功能清单，还必须写清楚最终开发效果和验收标准。

如果涉及页面、原型或视觉结构，计划必须说明：

- 页面模块顺序
- 关键阅读路径
- 主要区域的职责
- 关键 `id` / `class` / DOM 结构约束
- 允许和禁止的交互行为
- 不允许退化成什么样子

“不追求视觉效果”只能理解为“不做炫技、不做装饰性设计”，不能理解为“随便摆出来即可”。信息层级、可理解性、阅读路径仍然是验收项。

### 原型和截图必须入库

如果开发目标依赖原型、截图或视觉参考，参考材料不能只放在 `/private/tmp` 或对话上下文里。

应放入仓库，例如：

```text
docs/prototypes/
```

开发计划必须引用这些文件作为唯一视觉参考。执行模型不能凭记忆或自由理解重画页面。

### 测试必须约束结构和体验

前端测试不能只检查函数名、文案或文件是否存在。应尽量约束：

- 模块顺序
- 关键 DOM 容器
- 关键 `class` / `id`
- 状态切换后的可见结构
- 原型中不可缺少的信息层级

源码级测试不能替代浏览器验证，但可以防止实现退回到低质量的平铺展示。

### 浏览器验收不能用源码检查替代

`browser manual smoke: PASS` 必须来自真实浏览器或等价运行环境验证，不能只用 HTML/CSS/JS 源码检查代替。

浏览器验收至少确认：

- 页面真实渲染不是空白
- 关键模块顺序正确
- 主要交互可以操作
- 状态切换后详情区域正确更新
- 浏览器 console 没有 JavaScript error

如果执行模型没有真实浏览器验证能力，必须写 `NOT RUN`，并说明原因，不能写 `PASS`。

### 推荐协作流程

后续版本开发优先采用：

```text
Codex 定义目标、原型、验收标准
-> DeepSeek 按计划执行开发
-> Codex 独立测试和验收
-> DeepSeek 修复明确问题
-> Codex 最终收敛和提交
```

DeepSeek 适合按详细计划执行，不适合自主规划产品体验。涉及体验、页面结构或解释性展示时，Codex 必须先把目标效果、原型资产和验收标准固化到项目文档里。

## 技术约定

- Python 最低版本：3.10+
- V0.1 优先使用标准库
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
