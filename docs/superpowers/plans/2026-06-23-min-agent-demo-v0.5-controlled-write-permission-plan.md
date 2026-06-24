# Min Agent Demo V0.5 Controlled Write Permission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the Agent propose writing a new text file inside the configured workspace, require explicit CLI approval before the write happens, and show the permission request, approval/rejection, write result, and final answer in the Trace Viewer.

**Architecture:** V0.5 adds one controlled side-effect tool, `write_file`, and one permission gate in `AgentLoop`. Decision models may request `write_file`, but they still cannot execute tools directly. The CLI owns user approval, `ToolRegistry` still owns tool execution, `TraceRecorder` still owns observability, and the Trace Viewer remains read-only.

**Tech Stack:** Python 3.10+ standard library, existing `unittest` test suite, existing `AgentLoop` / `ToolRegistry` / `TraceRecorder`, vanilla Trace Viewer HTML/CSS/JS, no external dependencies.

---

## 0. Product Target

### V0.5 Name

```text
V0.5: 可控写文件权限
```

### One-Sentence Product Goal

让 Agent 可以在用户明确批准后，把综合结果写入 workspace 内的新文本文件，并在 Trace Viewer 中完整展示申请、确认、执行和结果。

### Why V0.5 Exists

V0.1-V0.4 已经证明了最小 Agent Loop、真实模型决策、多文件读取和可理解观察窗口。V0.5 要验证下一个关键机制：Agent 如何处理有副作用动作。

V0.5 不是要让 demo 变成 Claude Code。V0.5 只证明：

```text
Agent 可以提出写文件动作
-> 系统识别这是需要权限的工具
-> CLI 请求用户确认
-> 用户批准后才执行
-> 用户拒绝时不写文件
-> 全过程可观察、可复盘
```

---

## 1. Final User Experience

### Happy Path Demo

Run:

```bash
PYTHONPATH=src python3 -m min_agent.cli \
  "请阅读这个工作区里的资料，并生成 summary.md" \
  --workspace examples/workspace
```

Expected CLI flow:

```text
Trace viewer: http://127.0.0.1:8765/

Permission required: write_file
Path: summary.md
Reason: 需要把综合总结保存为文件
Preview:
<content preview>

Approve? [y/N] y

写入完成：summary.md
Run record: runs/<run-id>.json
```

Expected workspace result:

```text
examples/workspace/summary.md
```

The file content must be generated from read observations. It must not be a fixed hardcoded template that ignores the workspace files.

### Rejection Path Demo

Run the same command and answer `n` or press Enter.

Expected:

- No `summary.md` is created.
- The Agent produces a final answer explaining that the write was not approved.
- The run record and Trace Viewer show a permission request and rejection.

### Trace Viewer Final Shape

The viewer must remain read-only. It should show:

```text
任务入口
第 1 轮: Context -> Model -> Tool: list_dir -> Observation
第 2 轮: Context -> Model -> Tool: read_file -> Observation
第 3 轮: Context -> Model -> Tool: read_file -> Observation
第 N 轮: Context -> Model -> Permission Request
权限确认: User Approved or User Rejected
第 N+1 轮: Context -> Model -> Tool: write_file -> Observation
最终结果
任务完成
```

The exact number of read rounds can vary with the selected files, but the permission request and resolution must be visible.

---

## 2. Scope And Non-Goals

### In Scope

- Add one new workspace tool: `write_file`.
- Support creating one new UTF-8 text file inside workspace.
- Require CLI approval before executing `write_file`.
- Record permission request and permission result as structured trace events.
- Let FakeLLM demonstrate V0.5 offline without API key.
- Let DeepSeek request `write_file` as a local `AgentAction`.
- Update Trace Viewer to show permission events and the write-file flow.
- Add tests for safety, approval, rejection, trace, CLI, FakeLLM, DeepSeek prompt, and viewer source.
- Update docs and changelog.

### Out Of Scope

- Running shell commands.
- Editing existing files.
- Overwriting files.
- Appending to files.
- Writing multiple files in one action.
- Creating directories recursively.
- Patch/diff editing.
- Webpage-based approval.
- Trace Viewer controlling the Agent.
- Auto-approval.
- Writing `.env`.
- Reading or persisting API keys.
- Long-term memory.
- Multi-agent behavior.
- MCP, hooks, or plugin system.

### Safety Boundary

V0.5 may introduce side effects only through `write_file`, only after explicit CLI approval, only inside workspace, and only for a new text file.

---

## 3. File Boundaries

### Allowed To Modify

```text
AGENTS.md
CHANGELOG.md
README.md
docs/runbook.md
src/min_agent/agent_loop.py
src/min_agent/cli.py
src/min_agent/deepseek_llm.py
src/min_agent/fake_llm.py
src/min_agent/tool_registry.py
src/min_agent/tools/workspace.py
src/min_agent/types.py
web/trace_viewer.css
web/trace_viewer.html
web/trace_viewer.js
tests/test_agent_loop.py
tests/test_cli.py
tests/test_deepseek_llm.py
tests/test_fake_llm.py
tests/test_project_structure.py
tests/test_tool_registry.py
tests/test_trace_viewer_source.py
tests/test_types.py
tests/test_workspace_tools.py
```

### Allowed To Create

```text
tests/test_permission_flow.py
```

Only create this file if the existing `tests/test_agent_loop.py` becomes too large to keep permission-flow tests readable.

### Do Not Modify Unless A Test Proves It Is Necessary

```text
src/min_agent/context_builder.py
src/min_agent/deepseek_client.py
src/min_agent/decision_model.py
src/min_agent/trace_recorder.py
src/min_agent/trace_server.py
```

### Must Not Create

```text
.env
examples/workspace/summary.md
```

`summary.md` may be generated during manual smoke tests, but it must not be committed. If generated during verification, delete it after manual verification only if it was created by the current verification step and the user has not asked to keep it.

---

## 4. Data And Event Design

### EventPhase Extension

Modify `src/min_agent/types.py`.

Add phases:

```python
"permission_requested",
"permission_resolved",
```

Rationale:

- This is the core V0.5 behavior.
- It should not be hidden inside generic tool events.
- Trace Viewer can then show permission state explicitly.
- `EventPhase` is a `Literal[...]` type alias. Adding the two phases affects type checking and source tests, but it does not change runtime behavior by itself.

### Content Preview Rule

Use one shared preview rule for CLI output and `TraceEvent.input.preview`:

```text
Take the first 200 characters of write content.
If content is longer than 200 characters, append "..."
```

Implement a small helper instead of duplicating truncation logic:

```python
def preview_text(value: str, limit: int = 200) -> str:
    return value if len(value) <= limit else value[:limit] + "..."
```

The preview is for human review only. The actual `write_file` tool must receive the full `content` after approval.

### Permission Request Event

When `AgentLoop` sees an action for a tool whose `ToolSpec.requires_permission` is `True`, emit:

```python
self.recorder.emit(
    phase="permission_requested",
    status="waiting",
    title="请求权限：write_file",
    reason=action.reason,
    input={
        "tool_name": action.tool_name,
        "args": action.args,
        "preview": content_preview,
    },
    output={},
)
```

### Permission Resolved Event

If approved:

```python
self.recorder.emit(
    phase="permission_resolved",
    status="completed",
    title="权限已批准",
    reason="用户批准执行 write_file",
    input={"tool_name": action.tool_name, "args": action.args},
    output={"approved": True},
)
```

If rejected:

```python
self.recorder.emit(
    phase="permission_resolved",
    status="interrupted",
    title="权限被拒绝",
    reason="用户拒绝执行 write_file",
    input={"tool_name": action.tool_name, "args": action.args},
    output={"approved": False},
)
```

Do not execute `write_file` after rejection.

### Permission Rejection Observation

After rejection, append an `Observation` so the decision model can produce a final answer:

```python
Observation(
    tool_name="write_file",
    args=action.args,
    result=ToolResult(
        success=False,
        error="permission denied by user",
        metadata={"permission": "rejected"},
    ),
)
```

Then emit `observation_added` with that observation.

---

## 5. Tool Contract: `write_file`

Modify `src/min_agent/tools/workspace.py`.

Function:

```python
def write_file(workspace: Path | str, args: dict[str, Any]) -> ToolResult:
```

Args:

```json
{
  "path": "summary.md",
  "content": "text content",
  "mode": "create"
}
```

Rules:

- `path` must be a string.
- `content` must be a string.
- `mode` is optional and defaults to `"create"`.
- Only `"create"` is supported in V0.5.
- Empty or whitespace path is rejected.
- Path must stay inside workspace.
- Workspace must exist and be a directory.
- Parent directory must already exist.
- Existing target file is rejected.
- Target path cannot be a directory.
- Writes UTF-8 text.
- Returns structured metadata.

Successful result:

```python
ToolResult(
    success=True,
    content="wrote file: summary.md",
    metadata={
        "path": "summary.md",
        "bytes": 123,
        "mode": "create",
    },
)
```

Error examples:

```python
ToolResult(success=False, error="path must be a string")
ToolResult(success=False, error="content must be a string")
ToolResult(success=False, error="unsupported mode: overwrite")
ToolResult(success=False, error="path is outside workspace: ../summary.md")
ToolResult(success=False, error="file already exists: summary.md")
ToolResult(success=False, error="parent directory does not exist: missing")
```

---

## 6. Permission Architecture

### CLI Approval Callback

Add an approval callback in `src/min_agent/cli.py`.

Shape:

```python
def confirm_tool_call(tool_name: str, args: dict[str, object], reason: str) -> bool:
    ...
```

Behavior:

- Print tool name.
- Print path for `write_file`.
- Print reason.
- Print content preview using the shared 200-character preview rule from Section 4.
- Prompt:

```text
Approve? [y/N]
```

- Return `True` only for lowercase or uppercase `y`.
- Return `False` for Enter, `n`, or anything else.

### AgentLoop Dependency

Modify `AgentLoop.__init__` to accept:

```python
permission_callback: Callable[[AgentAction], bool] | None = None
```

Default:

```python
self.permission_callback = permission_callback or (lambda _action: False)
```

Why default reject:

- Tests can verify safety.
- A permissioned tool can never execute accidentally without a callback.

CLI integration note:

- `confirm_tool_call(tool_name, args, reason)` is a CLI-facing function.
- `AgentLoop` receives `permission_callback: Callable[[AgentAction], bool]`.
- In `cli.py`, wrap `confirm_tool_call` before passing it to `AgentLoop`, for example:

```python
permission_callback=lambda action: confirm_tool_call(
    action.tool_name,
    action.args,
    action.reason,
)
```

- Do not change `AgentLoop` to know about CLI prompt formatting.

### ToolSpec Permission Check

`ToolRegistry` already stores `ToolSpec.requires_permission`. Use existing registry information instead of hardcoding `write_file` in `AgentLoop`.

Current `ToolRegistry` only exposes `register()`, `list_specs()`, and `call()`. V0.5 must add direct spec lookup:

```python
def get_spec(self, name: str) -> ToolSpec | None:
```

Rules:

- `AgentLoop` must call `ToolRegistry.get_spec(action.tool_name)` before executing a tool.
- If the spec exists and `requires_permission` is `True`, `AgentLoop` must request permission before `ToolRegistry.call()`.
- If the spec is missing, preserve the existing unknown-tool failure path.
- Do not hardcode `write_file` in `AgentLoop`.
- Do not bypass `ToolRegistry`.

---

## 7. FakeLLM V0.5 Behavior

Modify `src/min_agent/fake_llm.py`.

### Trigger

FakeLLM should enter V0.5 write flow when the user goal contains a write intent and at least one Markdown target path.

Write-intent verbs:

```text
生成
写入
保存
create
write
save
```

Target path:

- Use existing Markdown path extraction.
- The target can be any workspace-relative `.md` file, such as `summary.md`, `report.md`, or `notes/summary.md`.
- V0.5 still only supports creating one new file, so if multiple candidate output files are named, choose the first write-intent target and document that behavior in tests.

### Planned Behavior

If the user asks to generate `summary.md` and no source files are named:

```text
list_dir
-> read_file relevant markdown files
-> write_file summary.md
-> final_answer
```

If the user asks to generate `report.md`, the same flow should write `report.md`.

If the target write was approved and succeeded:

```text
final_answer: 已生成 <target>.md
```

If permission was rejected:

```text
final_answer: 没有生成 <target>.md，因为用户拒绝了写文件权限。
success=False or success=True?
```

Use `success=False` for rejection, because the requested user goal was not completed.

### Generated Content

Content should be derived from successful `read_file` observations:

```markdown
# Summary

## usage.md
<short preview>

## project.md
<short preview>

## architecture.md
<short preview>
```

Do not hardcode final content independent of observations.

### Avoid Infinite Loop

After a rejected `write_file` observation, FakeLLM must not ask for `write_file` again. It should produce a final answer explaining rejection.

---

## 8. DeepSeek V0.5 Behavior

Modify `src/min_agent/deepseek_llm.py`.

System prompt must allow:

```json
{
  "kind": "tool_call",
  "tool_name": "write_file",
  "args": {
    "path": "summary.md",
    "content": "...",
    "mode": "create"
  },
  "reason": "Need to save the synthesized summary to a new workspace file"
}
```

Rules in prompt:

- Use `write_file` only when the user explicitly asks to create, write, save, or generate a file.
- `write_file` can only create a new text file.
- Do not request `.env`.
- Do not request workspace-external paths.
- Do not request overwrite.
- The model only proposes the action; local permission and tools decide execution.

Validation:

- Unknown tool still rejected.
- Invalid JSON still produces observable failure.
- Invalid action still produces observable failure.
- DeepSeek cannot bypass permission.

---

## 9. Trace Viewer V0.5 Requirements

Modify `web/trace_viewer.js`, `web/trace_viewer.css`, and only modify `web/trace_viewer.html` if a container is truly needed.

### Existing V0.4 Viewer Structure Must Be Preserved

Current V0.4 viewer already contains these important structures and tests:

```text
task-entry
task-completion
flow-overview
summary-panel
context-panel
round-index
round-status-dot
round-step-count
step-io-grid
raw-event
flow-node
```

Do not replace the viewer with a new layout. V0.5 must extend the current model:

- Keep `任务入口` as a standalone item.
- Keep `任务完成` as a standalone item.
- Keep Agentic Loop rounds grouped by `context_built`.
- Keep each round's `flow-overview`.
- Keep per-step input/output sections and `raw-event` JSON.
- Keep Trace Viewer read-only.

### Round Grouping Rules For Permission Events

`buildRounds()` must continue to start rounds only at `context_built`.

Permission events must not start a new Agentic Loop round.

Rules:

- `permission_requested` belongs to the current round, immediately after the `llm_decision` that requested the permissioned tool.
- `permission_resolved` belongs to the same current round.
- `run_started` remains outside rounds as `task-entry`.
- `run_completed`, `run_failed`, and `run_interrupted` remain outside rounds as `task-completion`.
- If a permission event appears before any `context_built`, place it in a system round instead of crashing.

### Round Flow Mapping

Extend current flow mapping and `buildFlowItems()`:

```text
permission_requested -> Permission Request
permission_resolved approved -> User Approved
permission_resolved rejected -> User Rejected
tool_started write_file -> Tool: write_file
```

Also extend `moduleForPhase()` consistently with current style:

```text
permission_requested -> Permission
permission_resolved -> Permission
```

Do not remove existing mappings for:

```text
run_started
context_built
llm_decision
tool_started
tool_finished
observation_added
final_answer
run_completed
run_failed
run_interrupted
```

### Details

Permission request detail must show:

- Tool name
- Path
- Reason
- Content preview
- Raw event JSON

Permission resolved detail must show:

- Approved or rejected
- Reason
- Raw event JSON

The details should use the existing `renderEventStep()` / `appendSection()` style so permission events visually match other steps.

### Summary Metrics

Use a fixed 5-column top metrics layout in V0.5:

```text
执行轮次
模型决策
工具调用
权限请求
观察结果
```

Replace the V0.4 separate `list_dir` and `read_file` metrics with one merged `工具调用` metric. Do not keep per-tool columns in V0.5, because adding `write_file` would otherwise crowd the top bar.

Counting rules:

- `执行轮次`: number of Agentic Loop rounds.
- `模型决策`: count of `llm_decision` events.
- `工具调用`: count of all `tool_started` events, including `list_dir`, `read_file`, and `write_file`.
- `权限请求`: count of `permission_requested` events.
- `观察结果`: count of `observation_added` events.

Do not create a visually noisy top bar.

### Read-Only Boundary

Do not add approve/reject buttons to the web page.

---

## 10. Task Breakdown

### Task 1: Extend Types And Source Tests

**Files:**

- Modify: `src/min_agent/types.py`
- Modify: `tests/test_types.py`

- [ ] Add `permission_requested` and `permission_resolved` to `EventPhase`.
- [ ] Add tests that construct `TraceEvent` with both phases and call `to_dict()`.
- [ ] Run:

```bash
python3 -m unittest tests.test_types
```

Expected:

```text
OK
```

### Task 2: Implement `write_file` Tool Tests First

**Files:**

- Modify: `tests/test_workspace_tools.py`

Add tests for:

- success creating `summary.md`
- default mode is create
- rejects non-string path
- rejects non-string content
- rejects unsupported mode
- rejects parent escape
- rejects absolute path outside workspace
- rejects existing file
- rejects missing parent directory
- rejects directory path

Run:

```bash
python3 -m unittest tests.test_workspace_tools
```

Expected before implementation:

```text
FAILED
```

Failure should be because `write_file` does not exist.

### Task 3: Implement `write_file`

**Files:**

- Modify: `src/min_agent/tools/workspace.py`

Implement `write_file` exactly according to Section 5.

Run:

```bash
python3 -m unittest tests.test_workspace_tools
```

Expected:

```text
OK
```

### Task 4: Register `write_file` In CLI

**Files:**

- Modify: `src/min_agent/cli.py`
- Modify: `tests/test_cli.py`

Add `write_file` to `build_tool_registry()` with:

```python
ToolSpec(
    name="write_file",
    description="Create a new UTF-8 text file inside the configured workspace after approval.",
    args_schema={"path": "string", "content": "string", "mode": "string"},
    requires_permission=True,
)
```

Add test:

```python
tool_names = {tool.name for tool in registry.list_specs()}
self.assertEqual(tool_names, {"read_file", "list_dir", "write_file"})
```

Also assert `write_file` spec has `requires_permission=True`.

Run:

```bash
python3 -m unittest tests.test_cli
```

Expected:

```text
OK
```

### Task 5: Add Permission Callback To AgentLoop

**Files:**

- Modify: `src/min_agent/agent_loop.py`
- Modify: `tests/test_agent_loop.py` or create `tests/test_permission_flow.py`
- Modify: `src/min_agent/tool_registry.py`
- Modify: `tests/test_tool_registry.py`

Step order:

1. Add failing tests for `ToolRegistry.get_spec(name)`.
2. Implement `ToolRegistry.get_spec(name) -> ToolSpec | None`.
3. Add failing permission-flow tests for `AgentLoop`.
4. Implement permission handling in `AgentLoop`.

`ToolRegistry.get_spec()` requirements:

- returns the registered `ToolSpec` for a known tool.
- returns `None` for an unknown tool.
- does not execute the tool.
- preserves existing `register()`, `list_specs()`, and `call()` behavior.

Test cases:

- permissioned tool is not executed when callback rejects.
- permission rejection emits `permission_requested`.
- permission rejection emits `permission_resolved` with `approved=False`.
- rejection creates an observation with `permission=rejected`.
- approved permission executes `write_file`.
- approved permission emits `permission_resolved` with `approved=True`.
- non-permission tools still execute without callback.

Run focused test:

```bash
python3 -m unittest tests.test_agent_loop
```

or:

```bash
python3 -m unittest tests.test_permission_flow
```

Expected:

```text
OK
```

### Task 6: Implement CLI Approval Prompt

**Files:**

- Modify: `src/min_agent/cli.py`
- Modify: `tests/test_cli.py`

Add prompt function and wire into `AgentLoop`.

Important signature boundary:

- Keep `confirm_tool_call(tool_name: str, args: dict[str, object], reason: str) -> bool` in the CLI layer.
- Wrap it into `Callable[[AgentAction], bool]` before passing to `AgentLoop`.
- `AgentLoop` should only receive and call the `AgentAction` callback; it should not import or know about the CLI prompt helper.

Test with patched `input()`:

- returns true for `y`
- returns true for `Y`
- returns false for empty input
- returns false for `n`
- preview is printed for write content
- preview truncates content longer than 200 characters and appends `...`
- preview does not truncate content of 200 characters or fewer

Run:

```bash
python3 -m unittest tests.test_cli
```

Expected:

```text
OK
```

### Task 7: Update FakeLLM For Offline V0.5 Demo

**Files:**

- Modify: `src/min_agent/fake_llm.py`
- Modify: `tests/test_fake_llm.py`

Tests:

- goal asking to generate `summary.md` eventually requests `write_file`.
- goal asking to generate `report.md` also requests `write_file` for `report.md`.
- write flow requires a write-intent verb plus a Markdown target path, not the literal `summary.md` string.
- write content includes previews from successful read observations.
- successful `write_file` observation leads to final answer mentioning the target file.
- rejected permission observation leads to final answer and does not request `write_file` again.
- if `write_file` unavailable, final answer fails clearly.

Run:

```bash
python3 -m unittest tests.test_fake_llm
```

Expected:

```text
OK
```

### Task 8: Update DeepSeek Prompt And Tests

**Files:**

- Modify: `src/min_agent/deepseek_llm.py`
- Modify: `tests/test_deepseek_llm.py`

Tests:

- system prompt includes `write_file`.
- system prompt says model only proposes action.
- parsed `write_file` action returns local `AgentAction`.
- unknown write-like action is rejected if not exactly `write_file`.

Run:

```bash
python3 -m unittest tests.test_deepseek_llm
```

Expected:

```text
OK
```

### Task 9: Update Trace Viewer

**Files:**

- Modify: `web/trace_viewer.js`
- Modify: `web/trace_viewer.css`
- Modify: `tests/test_trace_viewer_source.py`

Preserve existing V0.4 viewer structure. Extend these existing functions instead of replacing the viewer:

```text
buildRounds
buildRunSummary
moduleForPhase
buildFlowItems
renderEventStep
renderRoundList
renderRoundDetail
renderTaskEntryItem
renderTaskCompletionItem
```

CSS guidance:

- No new CSS rules are expected by default.
- Permission events should first reuse existing `event-step`, `step-io-grid`, `raw-event`, `flow-overview`, and `flow-node` styles.
- Only add CSS if permission details become unclear without distinct styling.
- Do not create a new visual system or a separate permission panel.

Source tests must assert:

- `permission_requested` appears in viewer source.
- `permission_resolved` appears in viewer source.
- `Permission Request` appears in flow labels.
- `User Approved` appears.
- `User Rejected` appears.
- `write_file` appears in viewer handling.
- `permission_requested` and `permission_resolved` are not treated like `run_started`, `run_completed`, `run_failed`, or `run_interrupted` in `buildRounds`.
- existing V0.4 structure tokens still exist:

```text
task-entry
task-completion
flow-overview
summary-panel
context-panel
round-index
round-status-dot
round-step-count
step-io-grid
raw-event
flow-node
```

- no approve/reject buttons are added to HTML.

Run:

```bash
python3 -m unittest tests.test_trace_viewer_source
```

Expected:

```text
OK
```

### Task 10: Update Docs And Version Rules

**Files:**

- Modify: `AGENTS.md`
- Modify: `CHANGELOG.md`
- Modify: `README.md`
- Modify: `docs/runbook.md`

AGENTS must add:

```markdown
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
```

CHANGELOG must be product-readable, not an engineering diff.

README must show the V0.5 demo command and explain approval.

runbook must include happy path and rejection path verification.

---

## 11. Full Verification

Run:

```bash
python3 -m unittest tests.test_types
python3 -m unittest tests.test_workspace_tools
python3 -m unittest tests.test_tool_registry
python3 -m unittest tests.test_cli
python3 -m unittest tests.test_agent_loop
python3 -m unittest tests.test_fake_llm
python3 -m unittest tests.test_deepseek_llm
python3 -m unittest tests.test_trace_viewer_source
python3 -m unittest discover -s tests
git diff --check
```

Expected:

```text
OK
```

### Happy Path Smoke

Make sure `summary.md` does not already exist.

Run:

```bash
PYTHONPATH=src python3 -m min_agent.cli \
  "请阅读这个工作区里的资料，并生成 summary.md" \
  --workspace examples/workspace \
  --no-viewer \
  --no-browser \
  --step-delay 0
```

When prompted, type:

```text
y
```

Expected:

- CLI asks for permission before writing.
- CLI exits `0`.
- `examples/workspace/summary.md` exists.
- File contains content based on workspace observations.
- Run record contains `permission_requested`.
- Run record contains `permission_resolved`.
- Run record contains `tool_started` for `write_file`.

After verification, remove generated `examples/workspace/summary.md` if it is untracked and was created only for this smoke test.

### Rejection Smoke

Make sure `summary.md` does not already exist.

Run the same command and answer:

```text
n
```

Expected:

- CLI asks for permission.
- No `examples/workspace/summary.md` exists.
- Final answer explains the user rejected write permission.
- Run record contains `permission_resolved` with `approved=False`.
- No `tool_started` for `write_file` occurs after rejection.

### Browser Smoke

Run with viewer enabled:

```bash
PYTHONPATH=src python3 -m min_agent.cli \
  "请阅读这个工作区里的资料，并生成 summary.md" \
  --workspace examples/workspace \
  --port 8765
```

In browser verify:

- Page is not blank.
- Permission request appears in the process.
- Permission decision appears separately.
- `write_file` appears only after approval.
- Rejection path shows no `write_file` tool execution.
- Flow overview includes permission nodes.
- Console has no JavaScript errors.

If browser verification cannot be run, report `NOT RUN` with reason. Do not write `PASS`.

---

## 12. Stop Conditions

Stop and report if any of these happen:

- Implementation requires running shell commands as an Agent tool.
- Implementation requires web approval buttons.
- Implementation writes files without CLI confirmation.
- Implementation writes outside workspace.
- Implementation overwrites existing files.
- Implementation writes `.env` or handles secrets.
- DeepSeek can bypass `ToolRegistry`.
- `write_file` is executed after user rejection.
- Tests require deleting user files.
- Browser smoke cannot be run but report says `PASS`.
- Any existing V0.1-V0.4 behavior breaks.

Report format:

```text
Blocked at: <task and step>
Reason: <specific problem>
Evidence: <test output, console error, or file/line>
Suggested next decision: <one concrete option>
```

---

## 13. Completion Report Format

After implementation and verification, report exactly:

```markdown
## V0.5 Completion Report

### Changed Files

- `src/min_agent/types.py`: <one sentence>
- `src/min_agent/tools/workspace.py`: <one sentence>
- `src/min_agent/agent_loop.py`: <one sentence>
- `src/min_agent/cli.py`: <one sentence>
- `src/min_agent/fake_llm.py`: <one sentence>
- `src/min_agent/deepseek_llm.py`: <one sentence>
- `web/trace_viewer.js`: <one sentence>
- `web/trace_viewer.css`: <one sentence>
- `tests/...`: <one sentence>
- docs files: <one sentence>

### Verification

- focused tests: <PASS/FAIL>
- `python3 -m unittest discover -s tests`: <PASS/FAIL>
- `git diff --check`: <PASS/FAIL>
- happy path write smoke: <PASS/FAIL>
- rejection smoke: <PASS/FAIL>
- browser smoke: <PASS/FAIL/NOT RUN with reason>

### Product Acceptance

- `write_file` creates new workspace file only: <yes/no>
- existing file overwrite rejected: <yes/no>
- CLI approval required before write: <yes/no>
- rejection prevents write: <yes/no>
- Trace shows permission request: <yes/no>
- Trace shows permission result: <yes/no>
- Trace Viewer remains read-only: <yes/no>
- FakeLLM offline demo works: <yes/no>
- DeepSeek can propose but not execute directly: <yes/no>

### Notes

- <Only actual caveats. Do not invent risks.>
```

Do not commit or push unless the user explicitly asks for it.
