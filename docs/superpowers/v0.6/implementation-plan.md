# min-agent-demo V0.6 详细开发计划

> 本文面向外部执行模型（DeepSeek），写清楚具体文件、接口、测试、运行命令、浏览器验收和不得退化的结构要求。
>
> 视觉参考：[trace-viewer-prototype.html](./trace-viewer-prototype.html)
> 问题参考：[context-source-layout-feedback.png](./context-source-layout-feedback.png)
> 产品设计：[product-design.md](./product-design.md)
> 项目规则：[AGENTS.md](../../../AGENTS.md)

---

## 一、最终效果

### 1.1 用户感知

用户运行：

```bash
PYTHONPATH=src python3 -m min_agent.cli \
  "请阅读这个工作区里的资料，并生成 summary.md" \
  --workspace examples/workspace
```

Agent 判断下一步前会自动加载：
- `<workspace>/minagent.md`（存在则注入，不存在则记录 not loaded）
- 最近 3 条 run record 摘要（存在则注入，损坏/缺失则跳过）
- 运行元信息（run_id、workspace、decision_model、启动时间）
- 工具目录（含权限标注）

Trace Viewer 每个轮次的 `Context Build` 步骤展示该轮模型判断前实际使用的完整上下文快照。页面先明确提示“本轮模型将使用 7 类上下文”，再按来源渲染 7 张独立卡片：5 张运行级基础上下文卡片、2 张逐轮动态上下文卡片。每张卡片拥有独立滚动区域，原始 Context JSON 默认折叠。

### 1.2 页面模块顺序（从上到下）

1. **Status Bar** — 任务标题 + 运行状态徽章
2. **Run Summary Grid** — 5 项统计：Agentic Loop 轮次、模型决策、工具调用、上下文构建、权限确认
3. **原始需求** — 用户输入的 goal
4. **最终结果** — final_answer 内容
5. **执行轮次（两栏布局）**
   - 左栏：轮次列表（Round 0 任务入口 + Round 1..N + 任务完成）
   - 右栏：轮次详情
     - 本轮流程概览（Context Build → Model Decision → ...）
     - 每个步骤的详细输入/输出

### 1.3 关键阅读路径

用户选择某个轮次 → 看到 `Context Build` 步骤 → 先看到“本轮模型将使用 7 类上下文” → 在来源卡片网格中分别查看 user_goal、workspace_config、run_memory、run_metadata、tool_catalog、working_observations、selected_project_content → 通过动态组顶部提示理解相对上一轮新增了什么 → 必要时展开原始 Context JSON → 下方 `Model Decision` 展示模型基于该快照做出的决策。

### 1.4 允许和禁止

**允许：**
- `Context Build` 步骤放在每个轮次详情内，与 `Model Decision` 一一对应
- 运行级基础上下文在所有轮次中内容一致（首次加载后沿用）
- 逐轮动态上下文随轮次递增而变化
- 7 类上下文使用独立卡片展示，卡片包含来源名称、状态、作用说明和可独立滚动的详情区域
- 当前用户目标在桌面端横跨两列并标记“最高优先级”
- 原始 Context JSON 保留为默认折叠的调试入口
- 顶部统计区展示"上下文构建"次数
- `minagent.md` 不存在时显示 "not loaded"
- run_memory 为空时显示 "暂无可用历史摘要"

**禁止：**
- 在原始需求和最终结果之间增加静态"上下文来源"区域
- 用一个脱离轮次的静态详情区代替逐轮快照
- 用两块聚合 JSON 或一个大 JSON 代替 7 张来源卡片
- 把 workspace_config 和 selected_project_content 合并为同一张卡片
- `Model Decision` 步骤中重复铺开完整上下文内容
- 页面控制 Agent、编辑配置、删除记录、批准权限
- 退化成平铺所有事件而不按轮次分组
- 读取 `AGENTS.md`、`CLAUDE.md` 或 workspace 外的配置文件

### 1.5 不允许退化成什么样子

- 不能把所有上下文来源堆在一个全局 JSON 面板里，用户无法区分各轮次差异
- 不能让用户阅读一整块 JSON 后自行判断来源边界
- 不能丢失来源卡片的独立滚动、状态标签、基础/动态分组和窄屏单列结构
- 不能丢失 `Context Build` 步骤，让用户看不到 Agent 判断依据
- 不能把 `workspace_config` 和 `selected_project_content` 混在一起展示
- 不能丢失"上下文构建"统计指标

---

## 二、涉及文件清单

### 2.1 新增文件

| 文件 | 说明 |
|------|------|
| `src/min_agent/context_loader.py` | 上下文加载器：负责读取 minagent.md、run memory、run_metadata、tool_catalog |
| `tests/test_context_loader.py` | 上下文加载器单元测试 |

### 2.2 修改文件

| 文件 | 改动范围 |
|------|----------|
| `src/min_agent/types.py` | 扩展 `AgentContext`，新增 `RunMetadata`、`WorkspaceConfig`、`RunMemorySummary`、`RunMemory`、`ToolCatalogEntry` |
| `src/min_agent/context_builder.py` | 集成 `ContextLoader`，区分运行级基础上下文和逐轮动态上下文 |
| `src/min_agent/agent_loop.py` | 维护 `selected_project_content` 路径列表；把 run_id、started_at 传给 ContextBuilder |
| `src/min_agent/cli.py` | 创建 ContextLoader，并注入 ContextBuilder |
| `src/min_agent/deepseek_llm.py` | `_user_prompt` 按产品设计的分层结构组织 prompt |
| `src/min_agent/trace_recorder.py` | 无需改动（context_built phase 已在 output 中携带完整上下文） |
| `web/trace_viewer.html` | 保持既有顶层容器和模块顺序；Context Build 来源卡片由 JS 动态写入 `#round-detail` |
| `web/trace_viewer.js` | `buildRunSummary` 增加 contextBuilds；把 context_built 渲染为 7 张来源卡片、动态变化提示和折叠原始 JSON；沿用独立 task-entry 作为唯一 Round 0 |
| `web/trace_viewer.css` | 新增来源卡片网格、来源状态、卡片内独立滚动、原始 JSON 折叠区和窄屏单列样式 |
| `tests/test_context_builder.py` | 扩展：覆盖新字段和上下文加载器集成 |
| `tests/test_deepseek_llm.py` | 扩展：验证 DeepSeek 实际 prompt 包含完整分层上下文和权限边界 |
| `tests/test_cli_scenarios.py` | 新增上下文注入场景测试 |
| `tests/test_trace_viewer_source.py` | 新增 V0.6 结构防退化检查 |
| `tests/test_agent_loop.py` | 新增 selected_project_content 追踪测试 |

### 2.3 可能生成的临时文件

- tests 运行中产生的临时 workspace 和 `minagent.md`
- 新的 run record JSON（在 `runs/` 下）

---

## 三、分模块实现指引

### 3.1 `src/min_agent/types.py` — 新增数据类型

在现有 dataclass 之后新增以下类型。**不要删除或重命名现有类型**。

```python
# ===== V0.6 新增类型 =====

@dataclass(frozen=True)
class RunMetadata:
    """本次运行的基础信息。"""
    run_id: str
    started_at: str
    workspace: str
    decision_model: str
    available_tool_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkspaceConfig:
    """workspace 根目录 minagent.md 的加载结果。"""
    status: str            # "loaded" | "not_found" | "error"
    path: str              # 固定为 "minagent.md"
    content: str = ""      # 实际注入模型的内容，最多 8000 字符
    preview: str = ""      # 展示用前 200 字符
    truncated: bool = False
    error: str = ""        # 安全错误码，不记录 workspace 外真实路径

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RunMemorySummary:
    """单条历史运行的摘要。"""
    run_id: str
    user_goal: str
    status: str
    final_answer_preview: str
    key_tool_chain: list[str]
    created_file_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RunMemory:
    """最近运行摘要的集合。"""
    status: str                  # "loaded" | "empty" | "error"
    summary_count: int
    summaries: list[RunMemorySummary] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary_count": self.summary_count,
            "summaries": [s.to_dict() for s in self.summaries],
        }


@dataclass(frozen=True)
class ToolCatalogEntry:
    """工具目录单项。"""
    name: str
    description: str
    requires_permission: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
```

**关键约束：**
- `WorkspaceConfig.status` 只能是 `"loaded"`、`"not_found"` 或 `"error"`
- `content` 才是实际进入 AgentContext 和 DeepSeek prompt 的配置内容；`preview` 只用于简要展示，不能代替 `content`
- 单次最多读取 8001 个字符：前 8000 个写入 `content`，多出的第 1 个字符只用于判断 `truncated=True`，避免无界读取
- 文件不可读、不是 UTF-8、指向 workspace 外时，返回 `status="error"`，不得让 CLI 崩溃，也不得在错误字段暴露 workspace 外真实路径
- `RunMemory.status` 只能是 `"loaded"`、`"empty"` 或 `"error"`
- `RunMemorySummary.key_tool_chain` 是从 run record events 中提取的工具调用链，例如 `["list_dir", "read_file", "write_file"]`

**扩展 `AgentContext`：**

在现有字段基础上新增以下字段：

```python
@dataclass(frozen=True)
class AgentContext:
    # === 既有字段（保持不变）===
    user_goal: str
    workspace: str
    available_tools: list[ToolSpec]
    observations: list[Observation]

    # === V0.6 新增字段 ===
    run_metadata: RunMetadata | None = None
    workspace_config: WorkspaceConfig | None = None
    run_memory: RunMemory | None = None
    tool_catalog: list[ToolCatalogEntry] = field(default_factory=list)
    selected_project_content: list[str] = field(default_factory=list)
```

`to_dict()` 方法同步更新，新增字段全部序列化。

---

### 3.2 `src/min_agent/context_loader.py` — 新建上下文加载器

**模块职责：** 从文件系统和 run records 中加载运行级基础上下文。不负责组装逐轮动态上下文。

```python
class ContextLoader:
    def __init__(self, workspace: str, runs_dir: str, decision_model: str):
        ...

    def load_workspace_config(self) -> WorkspaceConfig:
        """读取 <workspace>/minagent.md。
        文件不存在返回 status="not_found"。"""
        ...

    def load_run_memory(self, max_count: int = 3) -> RunMemory:
        """读取 runs_dir 下最近 max_count 条 run record 摘要。
        跳过损坏、缺字段或无法解析的文件。
        没有可用文件返回 status="empty"。"""
        ...

    def load_run_metadata(self, run_id: str, started_at: str, tool_count: int) -> RunMetadata:
        """组装本次运行的元信息。"""
        ...

    def build_tool_catalog(self, tools: list[ToolSpec]) -> list[ToolCatalogEntry]:
        """将 ToolSpec 列表转为 ToolCatalogEntry 列表。"""
        ...
```

**实现要点：**

1. `load_workspace_config`:
   - 初始化时先保存 `self._workspace_root = Path(workspace).resolve()`、`self._runs_dir`、`self._decision_model`
   - 候选路径固定为 `self._workspace_root / "minagent.md"`，不接受用户传入任意配置路径
   - 文件不存在 → `WorkspaceConfig(status="not_found", path="minagent.md")`
   - 文件存在时先 `resolve()`，确认真实路径仍 `is_relative_to(self._workspace_root)`；拒绝指向 workspace 外的 symlink
   - 以 UTF-8 文本模式最多读取 8001 个字符；`content=raw[:8000]`、`preview=content[:200]`、`truncated=len(raw) > 8000`
   - `PermissionError`、`OSError`、`UnicodeDecodeError` 或越界 symlink → `status="error"` 和安全错误码，不抛到 CLI
   - 不递归、不读取 `AGENTS.md`、`CLAUDE.md` 或其他配置文件

2. `load_run_memory`:
   - 列出 `runs_dir` 下所有 `.json` 文件
   - 逐个解析候选文件；跳过非 JSON、缺 `run_id`/`workspace`/`started_at`/`user_goal`/`status`/`events`、events 不是 list 的记录
   - 对记录中的 `workspace` 做规范化后，只保留与当前 `self._workspace_root` 相同的记录，禁止跨 workspace 注入历史上下文
   - 将有效同 workspace 记录按 `started_at` 降序排列，再取前 `max_count` 条；不能先截断文件列表再跳过损坏记录
   - 从 events 中提取 `key_tool_chain`：收集所有 `tool_started` phase 的 `input.tool_name`
   - 从 events 中提取 `final_answer` 的 `output.message` 前 200 字符作为 `final_answer_preview`
   - `created_file_path` 只能来自执行成功的 `write_file`：将 `tool_started(write_file)` 与其后的 `tool_finished(output.success=true)` 配对，并优先使用成功结果的 `output.metadata.path`；不能仅凭请求过写入动作就声称文件已创建
   - 没有任何有效记录 → `RunMemory(status="empty", summary_count=0, summaries=[])`
   - 单个文件异常只跳过该文件；只有 `runs_dir` 整体无法枚举或读取时返回 `status="error"`，且不使程序崩溃

3. `load_run_metadata`:
   - `run_id`、`started_at`、`tool_count` 来自参数
   - `workspace` 和 `decision_model` 分别来自初始化时保存的 `self._workspace_root`、`self._decision_model`
   - 不再从 `ContextBuilder.build()` 重复传递 `decision_model`

4. `build_tool_catalog`:
   - 遍历 `ToolSpec` 列表，创建 `ToolCatalogEntry`
   - `requires_permission` 字段直接透传

---

### 3.3 `src/min_agent/context_builder.py` — 扩展上下文构建器

```python
class ContextBuilder:
    def __init__(self, context_loader: ContextLoader | None = None):
        self._loader = context_loader
        self._run_metadata: RunMetadata | None = None
        self._workspace_config: WorkspaceConfig | None = None
        self._run_memory: RunMemory | None = None
        self._tool_catalog: list[ToolCatalogEntry] = []
        self._base_context_loaded = False

    def build(
        self,
        user_goal: str,
        workspace: str,
        available_tools: list[ToolSpec],
        observations: list[Observation],
        selected_project_content: list[str] | None = None,
        run_id: str = "",
        started_at: str = "",
    ) -> AgentContext:
        # 首次调用时加载运行级基础上下文（运行期间不变）
        if self._loader is not None and not self._base_context_loaded:
            self._workspace_config = self._loader.load_workspace_config()
            self._run_memory = self._loader.load_run_memory()
            self._tool_catalog = self._loader.build_tool_catalog(available_tools)
            self._run_metadata = self._loader.load_run_metadata(
                run_id=run_id,
                started_at=started_at,
                tool_count=len(available_tools),
            )
            self._base_context_loaded = True

        return AgentContext(
            user_goal=user_goal,
            workspace=workspace,
            available_tools=list(available_tools),
            observations=list(observations),
            run_metadata=self._run_metadata,
            workspace_config=self._workspace_config,
            run_memory=self._run_memory,
            tool_catalog=list(self._tool_catalog),
            selected_project_content=list(selected_project_content or []),
        )
```

**关键约束：**
- 运行级基础上下文只在首次 `build()` 时加载一次，后续轮次沿用缓存
- CLI 正常运行必须注入 `ContextLoader`；`ContextBuilder()` 无参数形式只为现有模块单元测试和兼容调用保留，此时新增运行级字段保持 `None`/空列表
- `build()` 签名新增可选的 `selected_project_content`、`run_id`、`started_at` 参数
- 不要改变老参数的类型和顺序（向后兼容）

---

### 3.4 `src/min_agent/agent_loop.py` — 维护 selected_project_content

**改动点：**

1. 新增 `_selected_project_content: list[str]` 实例变量，只保存成功读取过的 workspace 相对路径。完整正文仍以对应 `read_file` 的 `Observation.result.content` 为唯一来源，不重复存储。

2. `run()` 方法中：
   - 每次 `read_file` 成功后，将文件路径加入 `_selected_project_content`（去重）
   - 调用 `context_builder.build()` 时传入 `selected_project_content=self._selected_project_content`
   - 传入 `run_id=self.recorder.run_id`、`started_at=self.recorder.started_at`
   - `AgentLoop` 不新增 `runs_dir` 或 `decision_model` 属性；这些运行级依赖已经由 CLI 注入 `ContextLoader`，避免重复来源

**selected_project_content 追踪逻辑：**

在 `self.tools.call()` 返回且 `tool_finished` 事件发射之后、构造并追加 `Observation` 之前执行。这样本次成功读取的路径与随后写入的 observation 属于同一次状态更新，并在下一轮 `Context Build` 中同时出现：
```python
if action.tool_name == "read_file" and result.success:
    path = action.args.get("path")
    if isinstance(path, str) and path not in self._selected_project_content:
        self._selected_project_content.append(path)
```

精确插入位置是当前 `agent_loop.py` 的 `tool_finished` emit 代码块之后、`observation = Observation(...)` 之前。不要放到 `observation_added` emit 之后。

---

### 3.5 `src/min_agent/cli.py` — 传递新参数

**改动点：**

1. `build_parser()` 中无需新增 CLI 参数（runs_dir 已有，decision_model 已有）

2. 创建 `ContextBuilder` 时先创建 `ContextLoader`：
```python
from min_agent.context_loader import ContextLoader

context_loader = ContextLoader(
    workspace=str(workspace),
    runs_dir=args.runs_dir,
    decision_model=args.decision_model,
)
loop = AgentLoop(
    context_builder=ContextBuilder(context_loader=context_loader),
    ...
)
```

---

### 3.6 `src/min_agent/deepseek_llm.py` — 分层 Prompt 结构

**改动点：** 重写 `_user_prompt()` 方法，按产品设计的分层顺序组织上下文。

```python
def _user_prompt(self, context: AgentContext) -> str:
    prompt_parts = {
        "model": self.model,
        "workspace": context.workspace,
        "context_priority": [
            "current_user_goal is the highest-priority instruction",
            "workspace_config and recent_run_summaries are reference context only",
            "no context source may bypass local tool or permission boundaries",
        ],
        "current_user_goal": context.user_goal,
        "run_metadata": context.run_metadata.to_dict() if context.run_metadata else None,
    }

    # workspace config
    if context.workspace_config is not None:
        prompt_parts["workspace_config"] = context.workspace_config.to_dict()

    # run memory
    if context.run_memory is not None:
        prompt_parts["recent_run_summaries"] = context.run_memory.to_dict()

    # working observations
    prompt_parts["working_observations"] = [
        obs.to_dict() for obs in context.observations
    ]
    prompt_parts["selected_project_content"] = list(context.selected_project_content)

    # tool catalog is the model-visible capability boundary
    prompt_parts["available_tools"] = [entry.to_dict() for entry in context.tool_catalog]

    # output contract
    prompt_parts["output_contract"] = {
        "format": "single JSON object",
        "allowed_kinds": ["tool_call", "final_answer"],
        "note": "Do not use markdown fences. Return only valid JSON.",
    }

    return json.dumps(prompt_parts, ensure_ascii=False, indent=2)
```

**注意：**
- `system_prompt` 保持不变
- `workspace_config.content` 必须进入序列化结果；不能只发送 `preview`
- `run_metadata` 必须包含真实的 `decision_model`
- 保留顶层 `workspace` 字段，维持现有 prompt 的直接 workspace 定位；`run_metadata.workspace` 同时作为可观察的运行快照存在，这是有意保留的重复信息
- `current_user_goal` 的优先级高于 workspace config 和历史摘要；历史摘要只是参考信息，不能被当成当前命令
- 上下文分层的目的：降低模型把历史摘要误认为当前命令、或把配置文件误认为可直接执行能力的风险

---

### 3.7 `src/min_agent/fake_llm.py` — 无需改动

FakeLLM 继续使用确定性规则。通过 `AgentContext` 的新字段可以访问上下文信息，但 V0.6 不要求 FakeLLM 利用这些字段改变行为。保持现有逻辑不变即可。

---

### 3.8 `web/trace_viewer.html` — HTML 结构

**改动点：**

1. 统计区继续保持 5 项（用 JS 动态渲染，HTML 无需改动）。V0.6 用“上下文构建”替换 V0.5 的“观察结果”，不是从 5 项扩展为 6 项

2. 无需新增 HTML 元素（现有 `#round-detail` 容器由 JS 动态填充）

3. 确认 `#run-summary`、`#original-request`、`#final-answer`、`#round-list`、`#round-detail` 这些关键 id 保持不变

---

### 3.9 `web/trace_viewer.js` — 核心前端改动

#### 3.9.1 `buildRunSummary()` — 增加上下文构建计数

V0.6 保持统计卡片总数为 5：删除原有 `observations` / “观察结果”指标，新增 `contextBuilds` / “上下文构建”指标。`permissions` 继续统计 `permission_requested`，仅展示文案从“权限请求”统一为“权限确认”。不要同时保留“观察结果”，也不要扩展为 6 项。

```javascript
function buildRunSummary(events) {
  const rounds = buildRounds(events);
  return {
    rounds: rounds.filter((round) => round.events.some((event) => event.phase === "llm_decision")).length,
    modelCalls: events.filter((event) => event.phase === "llm_decision").length,
    toolCalls: events.filter((event) => event.phase === "tool_started").length,
    contextBuilds: events.filter((event) => event.phase === "context_built").length,
    permissions: events.filter((event) => event.phase === "permission_requested").length,
  };
}
```

#### 3.9.2 `renderRunSummary()` — 5 项指标

```javascript
const items = [
  ["Agentic Loop 轮次", summary.rounds],
  ["模型决策", summary.modelCalls],
  ["工具调用", summary.toolCalls],
  ["上下文构建", summary.contextBuilds],
  ["权限确认", summary.permissions],
];
```

#### 3.9.3 任务入口 — 沿用现有独立节点，不重复塞入 `buildRounds()`

当前 Viewer 已通过 `runStartedEvent()`、`renderTaskEntryItem()` 和 `renderTaskEntryDetail()` 单独展示任务入口。V0.6 必须沿用这条路径：

- `buildRounds()` 继续跳过 `run_started`、`run_completed`、`run_failed`、`run_interrupted`
- `renderTaskEntryItem()` 中 `.round-index` 的文案从 `"起"` 改为 `"0"`，标题继续使用“任务入口”
- 不新增 `round-0` 对象，避免任务入口在列表中出现两次
- `applyEvent(run_started)` 后的选中项仍为 `task-entry`
- 任务完成继续由独立的 `task-completion` 节点展示

#### 3.9.4 `renderEventStep()` — 特殊处理 context_built

当 `event.phase === "context_built"` 时，不使用默认的 `.step-io-grid` 输入输出布局，也不能把完整上下文合并成两块 JSON。必须按原型渲染来源卡片网格。

先新增通用卡片构造函数。所有模型或文件内容只能通过 `textContent` 写入，不得拼接 `innerHTML`：

```javascript
function createContextSourceCard({source, title, status, statusClass = "", summary, detail}) {
  const card = document.createElement("article");
  card.className = "context-source-card";
  card.dataset.source = source;

  const header = document.createElement("div");
  header.className = "context-source-card-header";
  const heading = document.createElement("h5");
  heading.textContent = title;
  const statusNode = document.createElement("span");
  statusNode.className = `context-source-status ${statusClass}`.trim();
  statusNode.textContent = status;
  header.append(heading, statusNode);

  const summaryNode = document.createElement("p");
  summaryNode.className = "context-source-summary";
  summaryNode.textContent = summary;

  const body = document.createElement("div");
  body.className = "context-source-body";
  body.tabIndex = 0;
  const detailNode = document.createElement("pre");
  detailNode.textContent = typeof detail === "string"
    ? detail
    : JSON.stringify(detail, null, 2);
  body.append(detailNode);

  card.append(header, summaryNode, body);
  return card;
}

function createContextSourceGroup(title, description) {
  const section = document.createElement("section");
  section.className = "context-source-group";
  const header = document.createElement("div");
  header.className = "context-source-group-heading";
  const heading = document.createElement("h4");
  heading.textContent = title;
  const descriptionNode = document.createElement("span");
  descriptionNode.textContent = description;
  header.append(heading, descriptionNode);
  const grid = document.createElement("div");
  grid.className = "context-source-grid";
  section.append(header, grid);
  return {section, grid};
}
```

`renderContextBuiltStep()` 必须按以下顺序构建内容：

```javascript
function selectedProjectPath(entry) {
  if (typeof entry === "object" && entry !== null) {
    return typeof entry.path === "string" ? entry.path : "";
  }
  return typeof entry === "string" ? entry : "";
}

function buildSelectedProjectContentText(output) {
  const entries = output.selected_project_content || [];
  if (entries.length === 0) {
    return "暂无已读取的项目文件";
  }

  const observations = output.observations || [];
  return entries.map((entry) => {
    const path = selectedProjectPath(entry);
    let content = "";
    for (let index = observations.length - 1; index >= 0; index -= 1) {
      const observation = observations[index];
      if (
        observation.tool_name === "read_file"
        && observation.args?.path === path
        && observation.result?.success === true
        && typeof observation.result?.content === "string"
      ) {
        content = observation.result.content;
        break;
      }
    }
    const displayedContent = content || "未找到对应的成功 read_file observation";
    return `${path}\n${"-".repeat(path.length)}\n${displayedContent}`;
  }).join("\n\n");
}

function buildContextChange(event, allEvents) {
  const snapshots = allEvents
    .filter((item) => item.phase === "context_built" && item.step < event.step)
    .sort((a, b) => a.step - b.step);
  const previous = snapshots[snapshots.length - 1];
  if (!previous) {
    return ["首轮，无前序上下文"];
  }

  const currentObservations = event.output?.observations || [];
  const previousObservations = previous.output?.observations || [];
  const currentFiles = event.output?.selected_project_content || [];
  const previousFiles = previous.output?.selected_project_content || [];
  const previousPaths = new Set(previousFiles.map(selectedProjectPath));
  const addedFiles = currentFiles
    .map(selectedProjectPath)
    .filter((path) => path && !previousPaths.has(path));
  const changes = [];
  if (currentObservations.length > previousObservations.length) {
    changes.push(`新增 ${currentObservations.length - previousObservations.length} 条 observation`);
  }
  if (addedFiles.length > 0) {
    changes.push(`新增已读取文件：${addedFiles.join(", ")}`);
  }
  return changes.length > 0 ? changes : ["与上一轮相比无新增动态上下文"];
}

function renderContextBuiltStep(container, event, allEvents) {
  const output = event.output || {};

  const intro = document.createElement("section");
  intro.className = "context-build-intro";
  const introCopy = document.createElement("div");
  const introTitle = document.createElement("h4");
  introTitle.textContent = "本轮模型将使用 7 类上下文";
  const introDescription = document.createElement("p");
  introDescription.textContent = "每个来源独立展示；卡片内容可单独上下滚动，看到的就是本轮判断前实际加入的上下文。";
  introCopy.append(introTitle, introDescription);
  const sourceCount = document.createElement("span");
  sourceCount.className = "context-source-count";
  sourceCount.textContent = "5 类基础 · 2 类动态";
  intro.append(introCopy, sourceCount);

  const base = createContextSourceGroup(
    "运行级基础上下文 · 本轮沿用",
    "运行开始时加载一次，每轮继续提供给模型",
  );
  base.grid.append(
    createContextSourceCard({
      source: "goal",
      title: "当前用户目标",
      status: "最高优先级",
      statusClass: "priority",
      summary: "用户本次明确输入，其他上下文只能辅助理解，不能覆盖这个目标。",
      detail: output.user_goal || "",
    }),
    createContextSourceCard({
      source: "workspace-config",
      title: "Workspace Config · minagent.md",
      status: output.workspace_config?.status || "Not loaded",
      statusClass: output.workspace_config?.status === "loaded" ? "loaded" : "",
      summary: "来自 workspace 根目录的规则和偏好，不改变本地权限边界。",
      detail: output.workspace_config || null,
    }),
    createContextSourceCard({
      source: "run-memory",
      title: "最近运行摘要",
      status: `${output.run_memory?.summary_count || 0} 条历史`,
      summary: "只读取当前 workspace 最近的有效记录，作为辅助背景。",
      detail: output.run_memory || {status: "empty", summaries: []},
    }),
    createContextSourceCard({
      source: "run-metadata",
      title: "运行元信息",
      status: "本轮沿用",
      summary: "帮助解释这次运行环境，不会直接触发任何工具。",
      detail: output.run_metadata || null,
    }),
    createContextSourceCard({
      source: "tool-catalog",
      title: "工具目录",
      status: "含权限边界",
      statusClass: "permission",
      summary: "模型只能提出这些本地动作，工具执行仍由 ToolRegistry 控制。",
      detail: output.tool_catalog || [],
    }),
  );

  const dynamic = createContextSourceGroup(
    "逐轮动态上下文 · 截至本轮",
    "工具结果只影响下一轮及后续判断",
  );
  const change = document.createElement("div");
  change.className = "context-change";
  change.textContent = buildContextChange(event, allEvents).join("；");
  dynamic.section.insertBefore(change, dynamic.grid);
  const selectedProjectContent = output.selected_project_content || [];
  const selectedProjectContentText = buildSelectedProjectContentText(output);
  dynamic.grid.append(
    createContextSourceCard({
      source: "observations",
      title: "Working Observations",
      status: `${(output.observations || []).length} 条 · 本轮动态`,
      summary: "Agent 已经获得的真实工具结果，是下一步判断的工作状态。",
      detail: output.observations || [],
    }),
    createContextSourceCard({
      source: "project-content",
      title: "Selected Project Content",
      status: `${selectedProjectContent.length} files`,
      summary: "通过 read_file 进入上下文的任务材料，与 minagent.md 配置分开。",
      detail: selectedProjectContentText,
    }),
  );

  const raw = document.createElement("details");
  raw.className = "raw-context";
  const rawSummary = document.createElement("summary");
  rawSummary.textContent = "原始 Context JSON · 调试信息（默认折叠）";
  const rawPre = document.createElement("pre");
  rawPre.textContent = JSON.stringify(output, null, 2);
  raw.append(rawSummary, rawPre);

  container.append(intro, base.section, dynamic.section, raw);
}
```

关键结构约束：

- 必须恰好创建 7 张 `.context-source-card`，`data-source` 分别为 `goal`、`workspace-config`、`run-memory`、`run-metadata`、`tool-catalog`、`observations`、`project-content`
- `goal` 在桌面端横跨两列；其他来源保持两列网格，窄屏全部单列
- 每张卡片的 `.context-source-body` 独立 `overflow-y: auto`，不能让一个来源的长内容无限撑高整个 Context Build
- workspace config 的 `content`、`truncated` 和 `error` 状态必须能在所属卡片看到，不能只展示 preview
- `selected_project_content` 只保存路径；Selected Project Content 卡片必须根据路径从成功的 `read_file` observation 读取完整 `result.content`，不能展示 200 字符 preview，也不能复制第二份正文到 AgentContext
- 原始 JSON 使用未设置 `open` 属性的 `<details>`，确保默认折叠

`renderEventStep()` 调用该分支时必须传入 `state.events`：

```javascript
if (event.phase === "context_built") {
  renderContextBuiltStep(container, event, state.events);
  return;
}
```

#### 3.9.5 `moduleForPhase()` — 增加 context_built 映射

```javascript
"context_built": "Context",
```

#### 3.9.6 `buildFlowItems()` — 增加 Context Build 节点

修改 `web/trace_viewer.js` 当前 `buildFlowItems()` 内的 `context_built` 分支（现有源码约第 521—523 行），只改展示标签：

```javascript
if (event.phase === "context_built") {
  add("Context Build");
}
```

不要修改 `moduleForPhase()` 的模块分类值；它仍保持 `"context_built": "Context"`。`Context Build` 是本轮流程节点名称，`Context` 是事件所属模块，两者职责不同。

---

### 3.10 `web/trace_viewer.css` — 新增来源卡片和独立滚动样式

`.run-summary-grid` 已经是 5 列，不需要修改。必须参照 `trace-viewer-prototype.html` 新增以下样式，类名和职责不得自行改写：

- `.context-build-intro`、`.context-source-count`：7 类来源说明和 5 类基础/2 类动态计数
- `.context-source-group`、`.context-source-group-heading`：基础与动态生命周期分组
- `.context-source-grid`：桌面端 `repeat(2, minmax(0, 1fr))`
- `.context-source-card`：来源卡片边界；使用 `data-source` 区分顶部颜色
- `.context-source-card[data-source="goal"]`：桌面端 `grid-column: 1 / -1`
- `.context-source-card-header`、`.context-source-status`、`.context-source-summary`：标题、状态和作用说明
- `.context-source-body`：固定高度、`overflow-y: auto`、`overscroll-behavior: contain`，并允许键盘聚焦
- `.context-change`：相对上一轮的动态变化提示
- `.raw-context`：默认折叠的原始 Context JSON

必须保留原型中的来源颜色语义：goal 蓝色、workspace config 绿色、run memory 紫色、run metadata 灰色、tool catalog 橙色、observations 青色、project content 黄色。颜色只用于帮助区分来源，不能替代文字标题和状态。

在现有 `@media (max-width: 800px)` 中把 `.context-source-grid` 改为单列，并把 goal 卡片的 `grid-column` 恢复为 `auto`。不得引入横向滚动。

由于卡片详情由 `createContextSourceCard()` 内的 `<pre>` 承载，必须增加 `.context-source-body pre` 局部覆盖：`margin: 0`、`padding: 0`、`border: 0`、`background: transparent`、`max-height: none`。滚动责任只属于 `.context-source-body`，不能再让内部 `<pre>` 形成第二层滚动条。

---

## 四、关键 DOM / class / id 约束

以下 id 必须保持存在，否则 `test_trace_viewer_source.py` 的防退化测试会失败：

| id / class | 说明 |
|------------|------|
| `#run-summary` | 运行统计容器 |
| `.summary-item` | 统计项卡片 |
| `.summary-value` | 统计数值 |
| `.summary-label` | 统计标签 |
| `#original-request` | 原始需求文本 |
| `#final-answer` | 最终结果文本 |
| `#round-list` | 轮次列表容器 |
| `#round-detail` | 轮次详情容器 |
| `.round-list li button` | 轮次选择按钮（可点击） |
| `.round-index` | 轮次序号 |
| `.round-title` | 轮次标题 |
| `.round-step-count` | 轮次步骤数 |
| `.flow-overview` | 本轮流程概览 |
| `.flow-node` | 流程节点 |
| `.event-step` | 事件步骤卡片 |
| `.event-step-number` | 步骤序号 |
| `.event-step-header` | 步骤头部 |
| `.step-io-grid` | 输入输出双栏布局 |
| `.detail-section` | 详情子区域 |

新增 class（原型中已有，需在 JS 渲染中确保使用）：

| class | 说明 |
|-------|------|
| `.round-list .active` | 当前选中轮次的高亮状态 |
| `.context-build-intro` | 本轮 7 类上下文说明 |
| `.context-source-count` | 5 类基础、2 类动态计数 |
| `.context-source-group` | 基础或动态来源分组 |
| `.context-source-group-heading` | 分组标题和生命周期说明 |
| `.context-source-grid` | 来源卡片网格 |
| `.context-source-card` | 单个上下文来源卡片 |
| `.context-source-card-header` | 来源标题和状态区域 |
| `.context-source-status` | loaded、最高优先级、权限边界等状态 |
| `.context-source-summary` | 来源作用说明 |
| `.context-source-body` | 来源详情独立滚动区域 |
| `.context-change` | 相比上一轮的动态变化 |
| `.raw-context` | 默认折叠的原始 Context JSON |

`.context-source-card` 必须使用以下 `data-source` 值，不允许用数组序号或展示文案代替稳定标识：

```text
goal
workspace-config
run-memory
run-metadata
tool-catalog
observations
project-content
```

---

## 五、测试验收矩阵

### 5.1 机制单元测试

#### 5.1.1 `tests/test_context_loader.py`（新建）

| 测试用例 | 验证目标 | 对应架构红线 |
|----------|----------|-------------|
| `test_load_minagent_md_exists` | workspace 根目录有 `minagent.md` 时返回 status="loaded"，同时包含实际 content 和 preview | 文件工具边界 |
| `test_load_minagent_md_not_exists` | 文件不存在时返回 status="not_found"，不抛异常 | 文件不存在时收敛 |
| `test_load_minagent_md_rejects_external_symlink` | 根目录 minagent.md 是指向 workspace 外的 symlink 时返回 error，且不读取目标内容 | 安全性：不能越界 |
| `test_load_minagent_md_invalid_utf8_returns_error` | 非 UTF-8 配置返回可观察 error，不让 CLI 崩溃 | 失败收敛 |
| `test_load_minagent_md_truncates_at_8000_chars` | content 最多 8000 字符并设置 truncated=true，preview 仍为 200 字符 | 上下文大小边界 |
| `test_load_run_memory_with_valid_records` | 有效的 run records 返回 status="loaded"，summary_count=N | run memory 加载逻辑 |
| `test_load_run_memory_empty_dir` | 无 run record 时返回 status="empty" | 空状态收敛 |
| `test_load_run_memory_skips_corrupted` | 损坏 JSON 被跳过，不影响正常记录加载 | 容错性 |
| `test_load_run_memory_skips_missing_fields` | 缺少 user_goal/status/events 的记录被跳过 | 容错性 |
| `test_load_run_memory_excludes_other_workspaces` | runs_dir 中其他 workspace 的记录不会进入当前上下文 | 上下文隔离 |
| `test_load_run_memory_collects_three_valid_records_after_skips` | 新记录损坏时继续向后扫描，仍最多收集最近 3 条有效同 workspace 记录 | 边界控制 |
| `test_created_file_path_requires_successful_write` | 只有成功的 write_file 结果才生成 created_file_path | 历史摘要真实性 |
| `test_build_tool_catalog_includes_permission` | write_file 条目的 requires_permission=true | 权限边界可见 |
| `test_build_tool_catalog_readonly_tools` | list_dir、read_file 条目的 requires_permission=false | 权限边界可见 |

#### 5.1.2 `tests/test_context_builder.py`（扩展）

| 测试用例 | 验证目标 |
|----------|----------|
| `test_build_context_contains_all_v06_fields` | 返回的 AgentContext 包含 run_metadata、workspace_config、run_memory、tool_catalog、selected_project_content |
| `test_base_context_loaded_only_once` | 第二次调用 build() 时不重新读取文件和 run records |
| `test_selected_project_content_passed_through` | selected_project_content 参数正确透传 |

#### 5.1.3 `tests/test_agent_loop.py`（扩展）

| 测试用例 | 验证目标 |
|----------|----------|
| `test_selected_project_content_tracks_read_files` | AgentLoop 在 read_file 成功后把文件路径加入 selected_project_content |
| `test_selected_project_content_no_duplicates` | 同一文件不重复加入 |
| `test_context_built_event_has_v06_fields` | context_built phase 的 TraceEvent output 中包含 V0.6 新增字段 |

#### 5.1.4 `tests/test_deepseek_llm.py`（扩展）

| 测试用例 | 验证目标 |
|----------|----------|
| `test_user_prompt_contains_full_layered_context` | prompt 包含顶层 workspace、current_user_goal、run_metadata、完整 workspace_config.content、recent_run_summaries、working_observations、selected_project_content、available_tools、output_contract |
| `test_user_prompt_preserves_context_priority` | prompt 明确当前用户目标优先，历史和配置不能覆盖当前目标或权限边界 |
| `test_user_prompt_includes_real_decision_model` | run_metadata.decision_model 与 CLI 选择一致 |
| `test_user_prompt_marks_write_file_permission` | available_tools 中 write_file 的 requires_permission=true |

#### 5.1.5 `tests/test_trace_viewer_source.py`（扩展）

这些测试是源码结构防退化测试，不代替浏览器验收。每个用例必须按函数区间截取源码后断言，避免只在整个文件中搜索一个恰好同名的字符串。

| 测试用例 | 验证目标 | 必须包含的具体断言 |
|----------|----------|--------------------|
| `test_summary_grid_replaces_observations_with_context_builds` | 统计总数保持 5，并用上下文构建替换观察结果 | 截取 `buildRunSummary` 到 `renderRunSummary`：包含 `contextBuilds` 和 `phase === "context_built"`，不再包含 `observations:`；截取 `renderRunSummary` 到 `buildRounds`：包含 `"上下文构建"`，不包含 `"观察结果"`，统计项数组恰好 5 项；CSS 包含 `grid-template-columns: repeat(5, minmax(0, 1fr))` |
| `test_render_context_built_has_seven_source_cards` | context_built 按原型渲染 7 个独立来源 | 截取 `renderContextBuiltStep`：包含“本轮模型将使用 7 类上下文”、基础/动态分组、`createContextSourceCard` 调用；源码包含 7 个稳定 `source` 值：goal、workspace-config、run-memory、run-metadata、tool-catalog、observations、project-content；不得再用 `.step-io-grid` 或两个聚合 JSON 作为 context_built 主展示 |
| `test_context_source_cards_have_independent_scroll` | 每个来源详情可独立滚动，窄屏为单列 | CSS 包含 `.context-source-body`、`overflow-y: auto`、`overscroll-behavior: contain`；`.context-source-grid` 桌面端为两列；800px media query 内为单列；goal 桌面端横跨两列、窄屏恢复 auto |
| `test_context_source_cards_render_status_and_raw_details` | 来源状态和原始 JSON 结构不丢失 | JS 包含 `.context-source-status`、priority、loaded、permission；原始 JSON 使用 `document.createElement("details")` 和 `.raw-context`，不设置 `open`；所有详情通过 `textContent` 写入，不使用 `innerHTML` |
| `test_task_entry_uses_zero_index_once` | 独立任务入口显示序号 0，buildRounds 仍跳过 run_started | `renderTaskEntryItem` 函数区间包含 `roundIndex.textContent = "0"`；`buildRounds` 的跳过列表仍包含 `run_started`；源码中不包含 `id: "round-0"`；`renderRoundList` 只调用一次 `renderTaskEntryItem(roundList, entry)` |
| `test_context_change_is_computed` | 动态差异来自相邻 context_built 快照比较 | `buildContextChange` 函数区间包含 `item.step < event.step`、`previous.output?.observations`、`previous.output?.selected_project_content` 和首轮文案；`renderContextBuiltStep` 使用 `buildContextChange(event, allEvents)`；不得出现“由前端比较前后轮次得出”占位文本 |
| `test_build_context_change_handles_object_entries` | 兼容开发期生成的 `{path, preview}` 旧条目 | `selectedProjectPath` 对字符串直接返回、对对象读取 `entry.path`；`buildContextChange` 的前后快照均通过该函数规范化，不能出现 `[object Object]` |
| `test_project_content_uses_full_read_file_observation_content` | 项目内容卡片展示完整正文而不是 preview | `buildSelectedProjectContentText` 必须匹配 `tool_name === "read_file"`、路径、`result.success`，并读取 `observation.result.content`；函数区间不得使用 `entry.preview`；`renderContextBuiltStep` 必须调用该函数 |
| `test_flow_uses_context_build_label` | 流程概览使用准确节点名称 | 截取 `buildFlowItems`：`context_built` 分支包含 `add("Context Build")`，不再包含 `add("Context")`；`moduleForPhase` 仍包含 `"context_built": "Context"` |
| `test_no_static_context_panel` | HTML 顶层不存在脱离轮次的静态上下文详情区 | HTML 不包含 `id="context-sources"`、`id="context-detail"`；仍满足 `#original-request` 在 `#final-answer` 前、`#final-answer` 在 `#round-list` 前；上下文快照只由 JS 写入 `#round-detail` |
| `test_key_dom_ids_present` | 关键容器没有被删除或改名 | 逐一断言 HTML 存在 `id="run-summary"`、`id="original-request"`、`id="final-answer"`、`id="round-list"`、`id="round-detail"`；JS/CSS 存在既有 round/flow/event 类和新增的 `context-build-intro`、`context-source-grid`、`context-source-card`、`context-source-body`、`context-change`、`raw-context` |

### 5.2 Agent 场景测试

#### 5.2.1 `tests/test_cli_scenarios.py`（扩展）

| 场景 | 用户目标 | CLI 参数 | 期望 run record 中的关键事件链 |
|------|----------|----------|-------------------------------|
| 带 minagent.md 的多文件总结 | "请阅读这个工作区里的资料，并生成 summary.md" | `--workspace <temporary-workspace> --runs-dir <temporary-runs> --decision-model fake` | run_started → context_built（output.workspace_config.status="loaded" 且 content 为测试写入的完整规则）→ llm_decision（tool_call: list_dir）→后续工具与 final_answer。 |
| 无 minagent.md 的任务 | "请阅读 notes.md 并总结" | `--workspace <temporary-workspace> --runs-dir <temporary-runs> --decision-model fake` | context_built（output.workspace_config.status="not_found"），任务正常完成。 |
| 有同 workspace 历史记录的任务 | "请总结 project.md" | `--workspace <temporary-workspace> --runs-dir <temporary-runs> --decision-model fake` | context_built（output.run_memory.status="loaded" 且只包含当前 workspace 的预置历史记录） |
| 写文件权限流程 | "读取 notes.md 并生成 output.md" | `--workspace <temporary-workspace> --runs-dir <temporary-runs> --decision-model fake` | permission_requested → permission_resolved（approved=true）→ tool_started（write_file）。V0.5 权限流程不受影响。 |
| 配置错误退出码 | 无效 workspace | `--workspace /nonexistent` | 退出码 2，不产生 run record |

以上场景必须使用 `tempfile.TemporaryDirectory()` 创建独立 workspace 和 runs_dir，不得在 `examples/workspace` 内创建、覆盖或删除测试文件。`contextBuilds` 是 Viewer 根据事件计算的展示值，不属于 run record 字段，因此只在前端测试和浏览器验收中验证。

**必须验证的工具出现/不出现清单：**
- `list_dir`、`read_file`、`write_file` → 可能出现
- `write_file` 必有 permission_requested 在其前面
- 不会出现 workspace 外的文件路径

### 5.3 浏览器验收

**所有 Trace Viewer 改动必须做真实浏览器验收。**

确认清单：

| # | 验收点 | 验证方式 |
|---|--------|----------|
| 1 | 页面真实渲染不是空白 | 打开浏览器，截图确认 |
| 2 | 统计区展示 5 项指标，含"上下文构建" | 肉眼检查 run-summary 区域 |
| 3 | 顶层不存在脱离轮次的静态"上下文来源"详情区 | 检查 original-request 和 result 之间没有额外 context 面板 |
| 4 | Round 0（Task Started）出现在轮次列表中 | 肉眼检查 round-list |
| 5 | 每个 Agentic Loop 轮次内部第一个步骤是 Context Build | 选择 Round 1，检查详情区流程概览 |
| 6 | Context Build 顶部明确显示“本轮模型将使用 7 类上下文”和“5 类基础 · 2 类动态” | 肉眼检查 Context Build 首屏 |
| 7 | 5 张基础来源卡片存在：当前用户目标、minagent.md、最近运行摘要、运行元信息、工具目录 | 逐张检查标题、状态、作用说明和详情 |
| 8 | 2 张动态来源卡片存在：Working Observations、Selected Project Content | 检查动态分组和相对上一轮变化提示 |
| 9 | 当前用户目标标记最高优先级；workspace config 与 selected project content 分属不同卡片 | 检查视觉层级和来源边界 |
| 10 | minagent.md、run memory、observations 和 selected project content 等长内容可以在各自卡片内独立上下滚动 | 使用超过 200 字符且包含末尾唯一标记的项目文件；确认 Selected Project Content 卡片能看到该标记，再分别滚动至少 3 张卡片，确认页面其他卡片内容不随之滚动 |
| 11 | 原始 Context JSON 默认折叠，展开后内容与本轮 context_built.output 一致 | 检查 `<details>` 初始关闭并手动展开 |
| 12 | 切换轮次后动态卡片和“相比上一轮”提示发生变化，历史轮次快照不被回写 | 选择 Round 1 → Round 2 → Round 3 对比 |
| 13 | 760px 或更窄视口下来源网格变为单列且无横向滚动 | 调整浏览器视口并滚动检查全部卡片 |
| 14 | Model Decision 步骤不重复铺开完整上下文 | 检查 Model Decision 的 input/output 区域 |
| 15 | 轮次选择按钮可点击，详情区正确更新 | 依次点击各轮次 |
| 16 | 浏览器 console 没有 JavaScript error | 打开 DevTools Console 检查 |

**验收命令：**

```bash
# 1. 建立独立手工验收 workspace；不修改 examples/workspace
SMOKE_WORKSPACE="$(mktemp -d /private/tmp/min-agent-v06-browser.XXXXXX)"
cp examples/workspace/notes.md "$SMOKE_WORKSPACE/notes.md"
printf '# min-agent rules\n- 生成总结文件时命名为 summary.md。\n' > "$SMOKE_WORKSPACE/minagent.md"

# 2. 启动带 trace viewer 的 Agent 任务；出现 write_file 权限请求时输入 y
PYTHONPATH=src python3 -m min_agent.cli \
  "请阅读这个工作区里的资料，并生成 summary.md" \
  --workspace "$SMOKE_WORKSPACE" \
  --runs-dir "$SMOKE_WORKSPACE/runs" \
  --decision-model fake \
  --keep-open-seconds 600

# 3. 在浏览器中打开显示的 URL
# 4. 按验收清单逐项检查
# 5. 打开 DevTools Console 确认无 error
# 6. 报告 $SMOKE_WORKSPACE 路径；未经用户确认不删除该目录
```

如果执行模型没有真实浏览器验证能力，必须写：
```
browser manual smoke: NOT RUN
原因：执行模型没有真实浏览器运行环境，无法打开浏览器验证页面渲染。
```
不能写 `PASS`。

### 5.4 工作区清理

| 产物 | 处理方式 |
|------|----------|
| 自动化测试的 workspace、minagent.md、输出文件和 runs_dir | 全部位于 `TemporaryDirectory`，由测试上下文自动清理；不得指向仓库内 `examples/workspace` 或根目录 `runs` |
| 浏览器手工验收 workspace 与 run records | 位于 `/private/tmp/min-agent-v06-browser.*`，验收结束后报告路径并保留；删除前必须取得用户确认 |
| 仓库 `examples/workspace/*`、`runs/*.json` | 本版本测试和浏览器验收都不新增、不覆盖、不删除 |

---

## 六、验证命令

**每次修改后必须运行：**

```bash
# 机制单元测试
python3 -m unittest discover -s tests

# 单独运行上下文加载器测试
python3 -m unittest tests.test_context_loader

# 单独运行上下文构建器测试
python3 -m unittest tests.test_context_builder

# DeepSeek prompt 结构测试（使用假客户端，不读取真实 API key、不访问网络）
python3 -m unittest tests.test_deepseek_llm

# Agent 场景测试
python3 -m unittest tests.test_cli_scenarios

# Trace Viewer 源码防退化测试
python3 -m unittest tests.test_trace_viewer_source

# 完整 smoke test（fake 模式）
PYTHONPATH=src python3 -m min_agent.cli \
  "请总结 notes.md 的内容" \
  --workspace examples/workspace \
  --runs-dir /private/tmp/min-agent-v06-smoke-runs \
  --decision-model fake \
  --no-viewer
```

---

## 七、实现顺序建议

按依赖关系推荐以下实现顺序：

1. **types.py** — 新增数据类型（无依赖）
2. **context_loader.py** — 上下文加载器（依赖 types.py）
3. **test_context_loader.py** — 先写加载、隔离、越界、截断和历史真实性失败测试
4. **context_loader.py** — 实现最小逻辑使加载器测试通过
5. **test_context_builder.py** — 先写缓存和兼容调用失败测试
6. **context_builder.py** — 扩展构建器并保留 `ContextBuilder()` 兼容路径
7. **test_agent_loop.py** — 先写 selected_project_content 与 context_built 事件失败测试
8. **agent_loop.py** + **cli.py** — 接通 ContextLoader、run metadata 和动态上下文
9. **test_deepseek_llm.py** — 先写完整 prompt、优先级和权限标注失败测试
10. **deepseek_llm.py** — 实现分层 prompt
11. **test_cli_scenarios.py** — 用临时 workspace/runs_dir 验证完整事件链
12. **test_trace_viewer_source.py** — 先写统计、单一 Round 0、动态差异和 DOM 结构失败测试
13. **trace_viewer.js** + **trace_viewer.css** — 按原型实现 7 张来源卡片、独立滚动、动态变化、折叠原始 JSON 和窄屏单列；HTML 只保持既有顶层容器
14. **完整 unittest** — 运行 `python3 -m unittest discover -s tests`
15. **浏览器验收** — 使用独立 `/private/tmp` workspace 完整手动验证

---

## 八、风险提示

1. **不要改动 TraceEvent 结构**。V0.4 规则明确：修改 TraceEvent 结构不在 V0.4 范围内，V0.6 也不应改动。所有新增上下文信息通过 `context_built` phase 的 `output` 字段承载。

2. **不要破坏现有权限流程**。V0.6 是增量，write_file 的 permission_requested → permission_resolved → tool_started 流程必须原封不动。

3. **不要改动 `examples/workspace/` 下现有示例文件**（notes.md、project.md、usage.md、architecture.md），也不要在该目录创建测试用 minagent.md 或输出文件。自动化测试必须使用 `TemporaryDirectory`。

4. **AgentContext 新增字段使用了 `| None` 语法**（`RunMetadata | None`），需要 `from __future__ import annotations` 在文件顶部。确认 existing types.py 已有此行。

5. **不要把 `preview` 当作实际上下文。** `workspace_config.content` 和 `truncated` 必须进入 `context_built.output` 与 DeepSeek prompt；Selected Project Content 的完整正文必须从成功的 `read_file` observation 获取，不能用 preview 代替，也不能在 AgentContext 中复制第二份正文。

6. **不要跨 workspace 读取 run memory。** 即使多个 workspace 共用同一个 runs_dir，也只能加载规范化 workspace 路径与当前运行一致的记录。

7. **不要重复创建任务入口。** Round 0 使用现有 `task-entry` 展示路径，`buildRounds()` 继续只负责 Agentic Loop Round 1..N。

8. **不要把 Context Build 退回聚合 JSON。** `trace-viewer-prototype.html` 是唯一视觉结构参考；7 个稳定来源、基础/动态分组、状态标签和独立滚动都是验收项，不是装饰性建议。

9. **不要用 `innerHTML` 渲染上下文内容。** minagent.md、历史摘要、observation 和模型相关字段都可能包含任意文本，必须使用 `textContent`，避免把内容解释成 DOM。
