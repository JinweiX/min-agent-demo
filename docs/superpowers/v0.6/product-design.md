# min-agent-demo V0.6 项目上下文注入产品功能设计

## 版本定位

V0.6 的主题是“项目上下文注入”。

这一版要解决的问题不是让 Agent 变成更复杂的自动化工具，而是让 Agent 在判断下一步前，能清楚拿到“本次任务是什么、当前 workspace 有什么规则、最近运行发生过什么、当前可用工具边界是什么”。

V0.6 的核心体验是：用户输入任务后，可以在 Trace Viewer 中看到 Agent 本轮决策到底参考了哪些上下文来源。

## 产品目标

V0.6 要让 demo 从“只观察执行过程”进一步走向“观察 Agent 的上下文来源”。

V0.5 已经验证了可控写文件权限。V0.6 在此基础上增加上下文供给层，让 Agent 的判断不只依赖用户输入和工具 observation，也能参考 workspace 根目录的配置说明、最近运行摘要、运行元信息和工具目录。

这仍然是一个机制 demo，不是生产级记忆系统，也不是小型 RAG 系统。

## 使用者能感受到什么

用户可以在 workspace 根目录放一个 `minagent.md`，用于描述这个 workspace 的任务规则、阅读偏好和边界。

例如：

```markdown
# min-agent workspace rules

- 回答前优先读取 project.md。
- 生成总结文件时命名为 summary.md。
- 不要把示例资料解释成生产环境能力。
```

用户运行：

```bash
PYTHONPATH=src python3 -m min_agent.cli \
  "请阅读这个工作区里的资料，并生成 summary.md" \
  --workspace examples/workspace
```

Agent 在判断下一步时，会把当前用户目标、`minagent.md`、最近运行摘要、运行元信息和工具目录一起作为上下文输入。随着工具执行，working observations 和已读取项目内容也会进入后续轮次。

Trace Viewer 应在每个 Agentic Loop 轮次的 `Context Build` 步骤中，把该轮模型判断前实际组装出的上下文按来源拆成 7 张独立卡片，而不是要求用户从两块大 JSON 中辨认来源：

```text
第 3 轮 / Context Build：

本轮模型将使用 7 类上下文

运行级基础上下文 · 本轮沿用
- 当前用户目标（最高优先级）
- Workspace Config · minagent.md
- 最近运行摘要
- 运行元信息
- 工具目录（含权限边界）

逐轮动态上下文 · 截至本轮
- Working Observations
- Selected Project Content
```

每张来源卡片必须显示来源名称、状态、作用说明和实际内容。长内容在卡片内部独立上下滚动。原始 Context JSON 保留在卡片区下方，但默认折叠，只作为调试入口。

如果 Agent 最终请求写文件，仍然必须走 V0.5 已有的 CLI 权限确认流程。

## 上下文系统分类

V0.6 设计中的 Agent 上下文可以分为以下几类。

### user_goal

用户本次输入的目标。

这是当前任务的最高优先级来源。其他上下文只能辅助理解任务，不能覆盖用户本次明确目标。

### run_metadata

本次运行的基础信息。

可包含：

- run id
- run started timestamp
- workspace path
- decision model
- available tool count

这类信息用于帮助用户和 Trace Viewer 理解本次运行环境，不用于绕过工具边界。

### workspace_config

workspace 根目录的配置文件。

V0.6 只读取：

```text
<workspace>/minagent.md
```

规则：

- 只读取 `--workspace` 根目录下的 `minagent.md`。
- 不递归查找。
- 不读取仓库根目录的 `AGENTS.md`。
- 不读取 `CLAUDE.md`。
- 不读取用户主目录或 workspace 外文件。
- 不自动创建、修改或补全 `minagent.md`。

`minagent.md` 是 demo workspace 内部的 Agent 配置文件，用于避免和 Codex、Claude 或仓库协作规则文件冲突。

### run_memory

最近运行摘要。

V0.6 只读取最近 N 条 run record 的摘要信息，建议默认 N 为 3。

摘要范围建议限制为：

- previous user goal
- run status
- final answer
- key tool chain
- created file path if available

run memory 是辅助背景，不是长期记忆系统。它不能自动改写项目规则，也不能替代当前用户目标。

### tool_catalog

当前 Agent 可用工具说明。

V0.6 可以把工具目录结构化放入上下文和 Trace Viewer 中，例如：

- `list_dir`: 只读列出 workspace 内目录，不递归
- `read_file`: 只读读取 workspace 内文件
- `write_file`: 创建 workspace 内新文本文件，需要权限确认

工具目录必须体现权限边界。模型只能提出本地 `AgentAction`，不能直接执行工具。

### working_observations

本轮运行过程中已经获得的 observation。

例如：

- `list_dir` 返回的目录列表
- `read_file` 返回的文件内容
- 用户批准或拒绝 `write_file`
- 工具执行失败信息

这一部分是现有 Agent Loop 的核心机制。V0.6 不需要重做，但需要在上下文展示中把它和启动时注入的上下文区分开。

### selected_project_content

Agent 通过工具读取到的项目内容。

这类内容不是启动时注入，而是在运行过程中通过 `read_file` 进入上下文。它和 `workspace_config` 必须区分：

- `workspace_config` 是规则和偏好。
- `selected_project_content` 是任务材料。

数据结构中，`selected_project_content` 只保存已成功读取的 workspace 相对路径，完整正文继续以对应 `read_file` 的 `Observation.result.content` 为唯一来源。Trace Viewer 根据路径匹配 observation，并在 Selected Project Content 卡片中展示完整正文；不能用 200 字符 preview 代替实际内容，也不在 AgentContext 中重复保存第二份正文。

## 上下文生命周期

V0.6 的上下文不是整次运行只有一份静态内容，而是由“运行级基础上下文”和“逐轮动态上下文”共同组成。

运行开始时加载一次的基础上下文包括：

- `user_goal`
- `run_metadata`
- `workspace_config`
- `run_memory`
- `tool_catalog`

这些内容在同一次运行中通常保持不变。后续每轮不需要重复读取配置文件和历史 run record，但需要继续放入该轮的上下文快照。

每轮随执行结果变化的动态上下文包括：

- `working_observations`
- `selected_project_content`

`AgentLoop` 在每次模型判断前都应执行一次 `Context Build`，把运行级基础上下文和截至当前轮次的动态上下文组合成完整快照。工具结果写入 observation 后，只影响下一轮及后续轮次的上下文，不能反向改变已经发生的模型判断。

## V0.6 纳入范围

V0.6 建议实际纳入以下四类上下文：

1. `workspace_config`
   - 读取 `<workspace>/minagent.md`。
   - 如果文件不存在，记录为 not loaded，不作为错误。

2. `run_memory`
   - 读取最近 3 条 run record 的摘要。
   - 跳过损坏、缺字段或无法解析的 run record。

3. `run_metadata`
   - 注入并展示本次运行基础信息。

4. `tool_catalog`
   - 结构化展示可用工具和权限要求。

`user_goal`、`working_observations`、`selected_project_content` 是既有 Agent 上下文的自然组成部分，V0.6 需要在命名和展示上显性化，但不把它们当作新增能力。

## V0.6 不做什么

V0.6 不做：

- 不执行命令。
- 不引入数据库。
- 不自动修改 `minagent.md`。
- 不读取 `AGENTS.md` 或 `CLAUDE.md`。
- 不递归搜索多层配置文件。
- 不读取环境变量上下文。
- 不读取密钥、token 或 `.env`。
- 不读取 git 状态。
- 不引入用户长期偏好。
- 不做文件自动索引。
- 不做 RAG。
- 不让页面控制 Agent。
- 不让配置文件绕过权限确认。
- 不让 run memory 覆盖当前用户目标。
- 不改变 V0.5 的写文件权限边界。

## Trace Viewer 预期效果

Trace Viewer 不在原始需求和最终结果之间增加一块整次运行共用的“上下文来源”区域。这样的静态区域会让用户误以为所有轮次看到的是同一份上下文。

上下文应放在每个 Agentic Loop 轮次详情的 `Context Build` 步骤中，并且与紧随其后的 `Model Decision` 一一对应。`Context Build` 的主阅读区域采用来源卡片网格：桌面端两列，窄屏单列。

卡片按生命周期分为两组：

1. 运行级基础上下文 · 本轮沿用
   - 当前用户目标：横跨桌面端两列，并显示“最高优先级”。
   - Workspace Config · minagent.md：显示 loaded、not loaded、error 或 truncated 状态以及实际注入内容。
   - 最近运行摘要：显示有效摘要数量和每条摘要。
   - 运行元信息：显示 run id、workspace、decision model、启动时间和工具数量。
   - 工具目录：显示工具用途、只读或权限确认边界。

2. 逐轮动态上下文 · 截至本轮
   - Working Observations：显示截至本轮累积的真实工具结果。
   - Selected Project Content：按文件路径匹配成功的 read_file observation，显示已选择任务材料的完整正文，与 minagent.md 配置分开。

动态上下文组顶部展示相对上一轮的变化，例如“新增 1 条 read_file observation，新增 3 个已读取文件”。首轮显示“首轮，无前序上下文”。

用户选择某个轮次后，可以看到：

- 该轮模型判断前的完整上下文来源。
- 本轮沿用的运行级基础上下文。
- 截至本轮已累积的 observation。
- 截至本轮已通过工具读取的项目内容。
- `minagent.md` 的加载状态、路径、完整注入内容和截断状态。
- run memory 的加载状态、摘要数量及摘要详情。
- 当前工具目录、用途和权限要求。
- 每个来源独立的视觉边界；长内容可以在所属卡片内滚动，不推动其他卡片内容。

卡片区下方保留“原始 Context JSON · 调试信息”，使用 `<details>` 默认折叠。顶部统计区可以展示“上下文构建”次数，但不能用一个静态详情区代替逐轮快照。`Model Decision` 步骤只展示模型实际输入摘要、模型返回内容和解析后的 `AgentAction`，不重复铺开完整上下文内容。

如果没有 `minagent.md`，页面应该明确显示未加载，而不是报错。

如果没有历史运行摘要，页面应该明确显示暂无可用历史摘要。

Trace Viewer 仍然是只读观察窗口，不能编辑配置文件、删除运行记录、批准权限或控制 Agent。

## DeepSeek Prompt 预期结构

DeepSeek 模式下，prompt 应分层表达上下文，建议顺序为：

1. Current user goal
2. Workspace config from `minagent.md`
3. Recent run summaries
4. Current working observations
5. Available tools and permission requirements
6. Local `AgentAction` JSON output contract

这样可以降低模型把历史摘要误认为当前命令，或把配置文件误认为可直接执行能力的风险。

FakeLLM 模式也应使用同一套结构化上下文对象，但可以继续保持确定性规则，不需要模拟真实模型语义理解。

## 验收方向

后续详细开发指引至少需要覆盖以下验收点。

### 机制单元测试

- `minagent.md` 只从 workspace 根目录读取。
- 文件不存在时不失败。
- workspace 外路径不能被配置读取逻辑访问。
- 损坏 run record 会被跳过。
- run memory 默认只读取最近 3 条摘要。
- tool catalog 能标明 `write_file` 需要权限。

### Agent 场景测试

- 带 `minagent.md` 的 workspace 运行后，run record 中出现 `workspace_config` 上下文来源。
- 没有 `minagent.md` 的 workspace 运行后，任务仍可正常完成。
- 有历史 run records 时，新运行能记录加载了 run memory。
- 写文件任务仍必须出现 `permission_requested -> permission_resolved -> tool_started(write_file)`。

### 浏览器验收

如果 Trace Viewer 改动，必须做真实浏览器验收，确认：

- 页面真实渲染不是空白。
- 顶层不存在脱离轮次的静态“上下文来源”详情区。
- 每个模型判断前都有对应的 `Context Build` 步骤。
- Context Build 顶部明确说明“本轮模型将使用 7 类上下文”。
- 5 张基础上下文卡片和 2 张动态上下文卡片均存在，来源名称、状态和详情清晰可见。
- 当前用户目标显示为最高优先级，workspace config 与 selected project content 不会混在一起。
- `minagent.md`、run memory、运行元信息、工具目录和权限要求都在各自卡片中可见。
- 每张长内容卡片可以独立上下滚动；原始 Context JSON 默认折叠。
- 切换轮次后，动态卡片内容和“相比上一轮”提示随快照变化，已经发生的轮次不会被回写。
- 桌面端为两列来源卡片网格，窄屏自动切换为单列。
- 主要交互可操作。
- 浏览器 console 没有 JavaScript error。

### 工作区清理

V0.6 可能生成：

- 新的 run record JSON。
- 测试用 workspace 内的 `minagent.md`。
- 写文件场景中的 `summary.md`。

生成的 run record 仍应默认忽略。测试产生的临时 workspace 应在测试内自动清理。删除手工生成文件前仍需遵守用户确认规则。

## 后续文档关系

本文是产品功能设计文档，用于固化 V0.6 的目标、范围和预期效果。

本版本的静态页面原型位于：

```text
docs/superpowers/v0.6/trace-viewer-prototype.html
```

原型中 Context Build 来源卡片网格是 V0.6 Viewer 的唯一视觉结构参考。问题反馈截图保存在：

```text
docs/superpowers/v0.6/context-source-layout-feedback.png
```

对应的详细开发指引文档位于：

```text
docs/superpowers/v0.6/implementation-plan.md
```

详细开发指引面向外部执行模型，写清楚具体文件、接口、测试、运行命令、浏览器验收和不得退化的结构要求，并以本节指定的静态原型为唯一视觉结构参考。
