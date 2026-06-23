# Min Agent Demo V3 Multi-File Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the demo Agent inspect a workspace directory, choose relevant Markdown files, read multiple files, and synthesize an answer while staying fully read-only.

**Architecture:** V3 adds one new safe local tool, `list_dir`, and updates the decision models so the loop can discover context before reading files. `AgentLoop` remains generic: it only records context, asks the decision model for an `AgentAction`, dispatches tool calls through `ToolRegistry`, stores observations, and repeats. DeepSeek and FakeLLM still only choose local actions; all file access remains inside the configured workspace.

**Tech Stack:** Python 3.10+ standard library, `pathlib`, `json`, `unittest`, existing `ToolRegistry`, existing `AgentLoop`, existing DeepSeek JSON action contract, vanilla Trace Viewer.

---

## 0. Scope And Non-Goals

### In Scope

- Add a read-only `list_dir` workspace tool.
- Register `list_dir` in CLI next to `read_file`.
- Make `FakeLLM` demonstrate V3 without a real model:
  - If the user goal does not name a specific Markdown file, call `list_dir`.
  - Read relevant Markdown files returned by `list_dir`.
  - Produce a final answer from multiple successful `read_file` observations.
- Update `DeepSeekLLM` system prompt so the model can choose either `list_dir` or `read_file`.
- Expand examples so V3 has multiple files to discover and summarize.
- Update docs and tests.
- Keep Trace Viewer read-only and compatible with the existing event stream.

### Out Of Scope

- Writing workspace files.
- Running shell commands.
- Recursive indexing or search.
- Embeddings, vector search, or ranking services.
- Long-term memory.
- Browser control from the Trace Viewer.
- Multiple agents or subagents.
- MCP, hooks, plugins, or tool marketplace behavior.
- Any `.env` creation or API key persistence.

### Product Boundary

V3 should teach this Agent path:

```text
Goal -> Context -> Model / Reasoning -> Tools(list_dir) -> Memory / State
     -> Model / Reasoning -> Tools(read_file) -> Memory / State
     -> Model / Reasoning -> final answer
```

V3 is not trying to be Claude Code. It is showing how an Agent discovers local context before choosing which read-only tools to call.

---

## 1. Target File Structure

Create:

```text
examples/workspace/project.md
examples/workspace/architecture.md
examples/workspace/usage.md
```

Modify:

```text
AGENTS.md
CHANGELOG.md
README.md
docs/runbook.md
src/min_agent/cli.py
src/min_agent/deepseek_llm.py
src/min_agent/fake_llm.py
src/min_agent/tools/workspace.py
tests/test_cli.py
tests/test_deepseek_llm.py
tests/test_fake_llm.py
tests/test_workspace_tools.py
```

Do not modify:

```text
src/min_agent/agent_loop.py
src/min_agent/tool_registry.py
src/min_agent/trace_recorder.py
src/min_agent/trace_server.py
web/trace_viewer.html
web/trace_viewer.css
web/trace_viewer.js
```

The viewer should already display new tool events because it renders the shared `TraceEvent` stream. Only touch viewer files if a test proves the current viewer cannot show V3 events.

---

## 2. Behavioral Design

### V3 Demo Command

Default fake mode should demonstrate V3 without a real API key:

```bash
PYTHONPATH=src python3 -m min_agent.cli \
  "请阅读这个工作区里的资料，并总结这个 demo 是怎么工作的" \
  --workspace examples/workspace
```

Expected high-level trace:

```text
1. 收到任务
2. 整理上下文
3. 决定下一步 -> list_dir
4. 调用工具：list_dir
5. 工具返回：list_dir
6. 吸收工具结果
7. 整理上下文
8. 决定下一步 -> read_file project.md
...
N. 生成最终回答
N+1. 任务完成
```

Specific file mode should still work:

```bash
PYTHONPATH=src python3 -m min_agent.cli \
  "请读取 notes.md 并总结" \
  --workspace examples/workspace
```

Expected: the Agent may go directly to `read_file` for `notes.md`, preserving the V1/V2 path.

### `list_dir` Tool Contract

Tool name:

```text
list_dir
```

Args:

```json
{"path": "."}
```

Rules:

- `path` is optional and defaults to `"."`.
- Empty string or whitespace also means `"."`.
- The resolved path must stay inside workspace.
- The path must exist.
- The path must be a directory.
- The tool is not recursive.
- Entries are sorted by name for deterministic tests and demos.
- The tool must not expose files outside workspace through symlink escapes.

Successful result:

```python
ToolResult(
    success=True,
    content="architecture.md\nnotes.md\nproject.md\nusage.md",
    metadata={
        "path": ".",
        "entries": [
            {"name": "architecture.md", "path": "architecture.md", "type": "file", "bytes": 120},
            {"name": "notes.md", "path": "notes.md", "type": "file", "bytes": 54},
            {"name": "project.md", "path": "project.md", "type": "file", "bytes": 130},
            {"name": "usage.md", "path": "usage.md", "type": "file", "bytes": 90},
        ],
    },
)
```

Error result examples:

```python
ToolResult(success=False, error="path is outside workspace: ../")
ToolResult(success=False, error="directory not found: missing")
ToolResult(success=False, error="path is not a directory: notes.md")
```

### FakeLLM V3 Decision Rules

FakeLLM remains deterministic, but it must not become a step-number script. It should decide from `AgentContext` and `Observation`.

Rules:

- If the user names one or more Markdown files, read those files.
- If the user does not name a Markdown file, call `list_dir` once for `"."`.
- If the user does not name a Markdown file and `list_dir` is unavailable, keep the V1/V2 failure behavior and ask for an explicit `.md` file path.
- After a successful `list_dir`, choose Markdown files from `metadata["entries"]`.
- Read up to 3 Markdown files to keep the demo short.
- If a planned file has no successful `read_file` observation, call `read_file`.
- If `read_file` is unavailable, return a failed final answer instead of requesting an unknown tool.
- If all planned reads succeeded, return a combined final answer.
- If `list_dir` fails, return a failed final answer.
- If no Markdown files are found, return a failed final answer explaining that no Markdown files were available.

### DeepSeek V3 Decision Rules

DeepSeek system prompt must allow two tools:

```json
{
  "kind": "tool_call",
  "tool_name": "list_dir",
  "args": {"path": "."},
  "reason": "Need to inspect available workspace files before choosing context"
}
```

```json
{
  "kind": "tool_call",
  "tool_name": "read_file",
  "args": {"path": "project.md"},
  "reason": "Need file content before answering"
}
```

Final answer contract remains unchanged:

```json
{
  "kind": "final_answer",
  "message": "Final answer text",
  "reason": "Enough information is available",
  "success": true
}
```

DeepSeek still cannot execute tools directly. It only returns JSON that the local `AgentLoop` routes through `ToolRegistry`.

---

## 3. Implementation Tasks

### Task 1: Add `list_dir` Workspace Tool

**Files:**

- Modify: `src/min_agent/tools/workspace.py`
- Test: `tests/test_workspace_tools.py`

- [ ] **Step 1: Write failing tests for successful directory listing**

Add to `tests/test_workspace_tools.py`:

```python
    def test_list_dir_success_inside_workspace(self) -> None:
        from min_agent.tools.workspace import list_dir

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "b.md").write_text("b", encoding="utf-8")
            (workspace / "a.md").write_text("a", encoding="utf-8")
            (workspace / "folder").mkdir()

            result = list_dir(workspace, {"path": "."})

        self.assertTrue(result.success)
        self.assertEqual(result.content, "a.md\nb.md\nfolder/")
        self.assertEqual(result.metadata["path"], ".")
        self.assertEqual(
            [entry["name"] for entry in result.metadata["entries"]],
            ["a.md", "b.md", "folder"],
        )
        self.assertEqual(result.metadata["entries"][0]["type"], "file")
        self.assertEqual(result.metadata["entries"][2]["type"], "directory")
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
python3 -m unittest tests.test_workspace_tools.WorkspaceToolsTest.test_list_dir_success_inside_workspace
```

Expected: fail because `list_dir` cannot be imported.

- [ ] **Step 3: Implement minimal `list_dir`**

Add to `src/min_agent/tools/workspace.py`:

```python
def list_dir(workspace: Path | str, args: dict[str, Any]) -> ToolResult:
    path_value = args.get("path", ".")
    if not isinstance(path_value, str):
        return ToolResult(success=False, error="path must be a string")
    if not path_value.strip():
        path_value = "."

    try:
        resolved = resolve_inside_workspace(workspace, path_value)
    except (FileNotFoundError, NotADirectoryError, PermissionError) as exc:
        return ToolResult(success=False, error=str(exc), metadata={"path": path_value})

    if not resolved.exists():
        return ToolResult(success=False, error=f"directory not found: {path_value}", metadata={"path": path_value})
    if not resolved.is_dir():
        return ToolResult(success=False, error=f"path is not a directory: {path_value}", metadata={"path": path_value})

    root = ensure_workspace(workspace)
    entries: list[dict[str, Any]] = []
    lines: list[str] = []
    for child in sorted(resolved.iterdir(), key=lambda item: item.name):
        child_resolved = child.resolve()
        if not child_resolved.is_relative_to(root):
            continue
        relative_path = str(child_resolved.relative_to(root))
        if child_resolved.is_dir():
            entry_type = "directory"
            display_name = f"{child.name}/"
            size = None
        else:
            entry_type = "file"
            display_name = child.name
            size = child_resolved.stat().st_size
        lines.append(display_name)
        entry: dict[str, Any] = {
            "name": child.name,
            "path": relative_path,
            "type": entry_type,
        }
        if size is not None:
            entry["bytes"] = size
        entries.append(entry)

    relative_dir = "." if resolved == root else str(resolved.relative_to(root))
    return ToolResult(
        success=True,
        content="\n".join(lines),
        metadata={"path": relative_dir, "entries": entries},
    )
```

- [ ] **Step 4: Run the test and verify it passes**

Run:

```bash
python3 -m unittest tests.test_workspace_tools.WorkspaceToolsTest.test_list_dir_success_inside_workspace
```

Expected: pass.

- [ ] **Step 5: Add safety and error tests**

Add to `tests/test_workspace_tools.py`:

```python
    def test_list_dir_defaults_to_workspace_root(self) -> None:
        from min_agent.tools.workspace import list_dir

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "notes.md").write_text("notes", encoding="utf-8")

            result = list_dir(workspace, {})

        self.assertTrue(result.success)
        self.assertEqual(result.metadata["path"], ".")
        self.assertIn("notes.md", result.content)

    def test_list_dir_rejects_parent_escape(self) -> None:
        from min_agent.tools.workspace import list_dir

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()

            result = list_dir(workspace, {"path": ".."})

        self.assertFalse(result.success)
        self.assertIn("outside workspace", result.error or "")

    def test_list_dir_rejects_absolute_path_outside_workspace(self) -> None:
        from min_agent.tools.workspace import list_dir

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            outside = Path(tmp) / "outside"
            outside.mkdir()

            result = list_dir(workspace, {"path": str(outside)})

        self.assertFalse(result.success)
        self.assertIn("outside workspace", result.error or "")

    def test_list_dir_rejects_file_path(self) -> None:
        from min_agent.tools.workspace import list_dir

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "notes.md").write_text("notes", encoding="utf-8")

            result = list_dir(workspace, {"path": "notes.md"})

        self.assertFalse(result.success)
        self.assertIn("not a directory", result.error or "")

    def test_list_dir_skips_symlink_escape_entries(self) -> None:
        from min_agent.tools.workspace import list_dir

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            outside = Path(tmp) / "outside.md"
            outside.write_text("secret", encoding="utf-8")
            (workspace / "safe.md").write_text("safe", encoding="utf-8")
            (workspace / "outside.md").symlink_to(outside)

            result = list_dir(workspace, {"path": "."})

        self.assertTrue(result.success)
        self.assertIn("safe.md", result.content)
        self.assertNotIn("outside.md", result.content)
```

- [ ] **Step 6: Run workspace tool tests**

Run:

```bash
python3 -m unittest tests.test_workspace_tools
```

Expected: all workspace tool tests pass.

Checkpoint: do not commit unless the user explicitly asks for commits during execution.

---

### Task 2: Register `list_dir` In CLI

**Files:**

- Modify: `src/min_agent/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI registration test**

Add to `tests/test_cli.py`:

```python
    def test_cli_registers_list_dir_tool(self) -> None:
        from min_agent.cli import build_tool_registry

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            registry = build_tool_registry(workspace)
            tool_names = [tool.name for tool in registry.list_specs()]

        self.assertIn("read_file", tool_names)
        self.assertIn("list_dir", tool_names)
```

If `build_tool_registry` does not exist yet, this test should fail with import or attribute error.

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
python3 -m unittest tests.test_cli.CliTest.test_cli_registers_list_dir_tool
```

Expected: fail because `build_tool_registry` is not defined or `list_dir` is not registered.

- [ ] **Step 3: Extract registry construction and register `list_dir`**

Modify `src/min_agent/cli.py` imports:

```python
from min_agent.tools.workspace import ensure_workspace, list_dir, read_file
```

Add this helper near `build_decision_model`:

```python
def build_tool_registry(workspace: Path) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="read_file",
            description="Read a UTF-8 text file inside the configured workspace.",
            args_schema={"path": "string"},
            requires_permission=False,
        ),
        lambda args: read_file(workspace, args),
    )
    registry.register(
        ToolSpec(
            name="list_dir",
            description="List files and directories inside the configured workspace.",
            args_schema={"path": "string"},
            requires_permission=False,
        ),
        lambda args: list_dir(workspace, args),
    )
    return registry
```

Replace the inline registry construction in `main()` with:

```python
        registry = build_tool_registry(workspace)
```

- [ ] **Step 4: Run the CLI registration test**

Run:

```bash
python3 -m unittest tests.test_cli.CliTest.test_cli_registers_list_dir_tool
```

Expected: pass.

- [ ] **Step 5: Run all CLI tests**

Run:

```bash
python3 -m unittest tests.test_cli
```

Expected: all CLI tests pass.

Checkpoint: do not commit unless the user explicitly asks for commits during execution.

---

### Task 3: Update FakeLLM For Multi-File Discovery

**Files:**

- Modify: `src/min_agent/fake_llm.py`
- Test: `tests/test_fake_llm.py`

- [ ] **Step 1: Add failing test for listing when no file is named**

Add to `tests/test_fake_llm.py`:

```python
    def test_lists_workspace_when_no_file_path_is_named(self) -> None:
        from min_agent.fake_llm import FakeLLM
        from min_agent.types import AgentContext, ToolSpec

        llm = FakeLLM()
        context = AgentContext(
            user_goal="请总结这个工作区",
            workspace="examples/workspace",
            available_tools=[
                ToolSpec(name="list_dir", description="List directory"),
                ToolSpec(name="read_file", description="Read file"),
            ],
            observations=[],
        )

        action = llm.decide(context)

        self.assertEqual(action.kind, "tool_call")
        self.assertEqual(action.tool_name, "list_dir")
        self.assertEqual(action.args, {"path": "."})
```

Update the old no-file-path test in `tests/test_fake_llm.py` so it explicitly covers the fallback when `list_dir` is unavailable:

```python
    def test_cannot_decide_without_file_path_when_list_dir_unavailable(self) -> None:
        from min_agent.fake_llm import FakeLLM
        from min_agent.types import AgentContext, ToolSpec

        llm = FakeLLM()
        context = AgentContext(
            user_goal="请总结一下",
            workspace="examples/workspace",
            available_tools=[ToolSpec(name="read_file", description="Read file")],
            observations=[],
        )

        action = llm.decide(context)

        self.assertEqual(action.kind, "final_answer")
        self.assertFalse(action.success)
        self.assertIn("无法判断", action.message or "")
```

Remove or replace the old `test_cannot_decide_without_file_path` name so it does not assert old behavior for a context where `list_dir` is available.

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
python3 -m unittest tests.test_fake_llm.FakeLLMTest.test_lists_workspace_when_no_file_path_is_named
```

Expected: fail because current FakeLLM returns final failure without a named Markdown file.

- [ ] **Step 3: Refactor target selection helpers**

Modify `src/min_agent/fake_llm.py` so the top constants and extraction helpers are:

```python
FILE_PATTERN = re.compile(r"[\w./-]+\.md")
MAX_FAKE_READS = 3
```

Replace `_extract_target_path` with:

```python
    def _extract_target_paths(self, user_goal: str) -> list[str]:
        matches = FILE_PATTERN.findall(user_goal)
        return list(dict.fromkeys(matches))
```

Update current single-file call site:

```python
        target_paths = self._extract_target_paths(context.user_goal)
```

- [ ] **Step 4: Add tool availability checks and list decision path**

Add this helper:

```python
    def _tool_available(self, context: AgentContext, tool_name: str) -> bool:
        return any(tool.name == tool_name for tool in context.available_tools)
```

Replace `decide()` with this structure:

```python
    def decide(self, context: AgentContext) -> AgentAction:
        target_paths = self._extract_target_paths(context.user_goal)
        if not target_paths:
            if not self._tool_available(context, "list_dir"):
                return AgentAction.final_answer(
                    message="无法判断需要读取哪个文件。请在任务中提供明确的 .md 文件名。",
                    reason="用户目标中没有可识别的 Markdown 文件路径，且 list_dir 工具不可用",
                    success=False,
                )
            listed = self._find_latest_observation(context.observations, "list_dir", {"path": "."})
            if listed is None:
                return AgentAction.tool_call(
                    tool_name="list_dir",
                    args={"path": "."},
                    reason="用户没有指定文件名，需要先查看 workspace 里有哪些资料",
                )
            if not listed.result.success:
                return AgentAction.final_answer(
                    message=f"查看目录失败：{listed.result.error}",
                    reason="无法获得 workspace 文件列表",
                    success=False,
                )
            target_paths = self._markdown_paths_from_listing(listed)[:MAX_FAKE_READS]
            if not target_paths:
                return AgentAction.final_answer(
                    message="workspace 中没有可总结的 Markdown 文件。",
                    reason="目录列表中没有 .md 文件",
                    success=False,
                )

        for target_path in target_paths[:MAX_FAKE_READS]:
            observation = self._find_latest_read_observation(context.observations, target_path)
            if observation is None:
                if not self._tool_available(context, "read_file"):
                    return AgentAction.final_answer(
                        message="无法读取文件：read_file 工具不可用。",
                        reason="需要读取文件内容，但当前上下文没有可用的 read_file 工具",
                        success=False,
                    )
                return AgentAction.tool_call(
                    tool_name="read_file",
                    args={"path": target_path},
                    reason=f"还没有 {target_path} 的内容，需要读取文件后才能综合回答",
                )
            if not observation.result.success:
                return AgentAction.final_answer(
                    message=f"读取文件失败：{observation.result.error}",
                    reason="工具没有返回可用于总结的文件内容",
                    success=False,
                )

        return AgentAction.final_answer(
            message=self._preview_multiple_files(target_paths[:MAX_FAKE_READS], context.observations),
            reason="已经获得相关文件内容，可以基于 observation 生成综合回答",
        )
```

Add helpers:

```python
    def _find_latest_observation(
        self,
        observations: list[Observation],
        tool_name: str,
        args: dict[str, str],
    ) -> Observation | None:
        for observation in reversed(observations):
            if observation.tool_name == tool_name and observation.args == args:
                return observation
        return None

    def _markdown_paths_from_listing(self, observation: Observation) -> list[str]:
        entries = observation.result.metadata.get("entries", [])
        if not isinstance(entries, list):
            return []

        paths: list[str] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if entry.get("type") != "file":
                continue
            path = entry.get("path")
            if isinstance(path, str) and path.endswith(".md"):
                paths.append(path)
        return paths

    def _preview_multiple_files(self, target_paths: list[str], observations: list[Observation]) -> str:
        previews: list[str] = []
        for target_path in target_paths:
            observation = self._find_latest_read_observation(observations, target_path)
            if observation is None:
                continue
            previews.append(self._preview_content(target_path, observation.result.content))
        return "；".join(previews)
```

Keep `_find_latest_read_observation()` and `_preview_content()` unless the new code requires a small signature change.

- [ ] **Step 5: Run the list decision test**

Run:

```bash
python3 -m unittest tests.test_fake_llm.FakeLLMTest.test_lists_workspace_when_no_file_path_is_named
python3 -m unittest tests.test_fake_llm.FakeLLMTest.test_cannot_decide_without_file_path_when_list_dir_unavailable
```

Expected: both pass.

- [ ] **Step 6: Add failing tests for reading files from listing and final synthesis**

Add to `tests/test_fake_llm.py`:

```python
    def test_reads_markdown_file_after_successful_listing(self) -> None:
        from min_agent.fake_llm import FakeLLM
        from min_agent.types import AgentContext, Observation, ToolResult, ToolSpec

        llm = FakeLLM()
        context = AgentContext(
            user_goal="请总结这个工作区",
            workspace="examples/workspace",
            available_tools=[
                ToolSpec(name="list_dir", description="List directory"),
                ToolSpec(name="read_file", description="Read file"),
            ],
            observations=[
                Observation(
                    tool_name="list_dir",
                    args={"path": "."},
                    result=ToolResult(
                        success=True,
                        content="architecture.md\nnotes.md",
                        metadata={
                            "entries": [
                                {"name": "architecture.md", "path": "architecture.md", "type": "file"},
                                {"name": "notes.md", "path": "notes.md", "type": "file"},
                            ]
                        },
                    ),
                )
            ],
        )

        action = llm.decide(context)

        self.assertEqual(action.kind, "tool_call")
        self.assertEqual(action.tool_name, "read_file")
        self.assertEqual(action.args, {"path": "architecture.md"})

    def test_final_answer_after_multiple_successful_reads(self) -> None:
        from min_agent.fake_llm import FakeLLM
        from min_agent.types import AgentContext, Observation, ToolResult, ToolSpec

        llm = FakeLLM()
        context = AgentContext(
            user_goal="请总结这个工作区",
            workspace="examples/workspace",
            available_tools=[
                ToolSpec(name="list_dir", description="List directory"),
                ToolSpec(name="read_file", description="Read file"),
            ],
            observations=[
                Observation(
                    tool_name="list_dir",
                    args={"path": "."},
                    result=ToolResult(
                        success=True,
                        content="architecture.md\nproject.md",
                        metadata={
                            "entries": [
                                {"name": "architecture.md", "path": "architecture.md", "type": "file"},
                                {"name": "project.md", "path": "project.md", "type": "file"},
                            ]
                        },
                    ),
                ),
                Observation(
                    tool_name="read_file",
                    args={"path": "architecture.md"},
                    result=ToolResult(success=True, content="# 架构\nAgentLoop 调度工具。"),
                ),
                Observation(
                    tool_name="read_file",
                    args={"path": "project.md"},
                    result=ToolResult(success=True, content="# 项目\n这是可观察 Agent demo。"),
                ),
            ],
        )

        action = llm.decide(context)

        self.assertEqual(action.kind, "final_answer")
        self.assertIn("architecture.md", action.message or "")
        self.assertIn("project.md", action.message or "")
```

- [ ] **Step 7: Run FakeLLM tests**

Run:

```bash
python3 -m unittest tests.test_fake_llm
```

Expected: all FakeLLM tests pass, including old specific-file behavior and the explicit `list_dir` unavailable fallback.

Checkpoint: do not commit unless the user explicitly asks for commits during execution.

---

### Task 4: Update DeepSeek Prompt For V3 Tools

**Files:**

- Modify: `src/min_agent/deepseek_llm.py`
- Test: `tests/test_deepseek_llm.py`

- [ ] **Step 1: Add failing prompt test**

Add to `tests/test_deepseek_llm.py`:

```python
    def test_system_prompt_allows_list_dir_tool(self) -> None:
        from min_agent.deepseek_llm import DeepSeekLLM

        llm = DeepSeekLLM(client=FakeClient('{"kind":"final_answer","message":"ok","reason":"done"}'), model="model")
        prompt = llm._system_prompt()

        self.assertIn('"tool_name": "list_dir"', prompt)
        self.assertIn('"args": {"path": "."}', prompt)
        self.assertIn('"tool_name": "read_file"', prompt)
```

If `FakeClient` does not exist in the file, add:

```python
class FakeClient:
    def __init__(self, content: str) -> None:
        self.content = content

    def create_chat_completion(self, system_prompt: str, user_prompt: str) -> str:
        return self.content
```

- [ ] **Step 2: Run the prompt test and verify it fails**

Run:

```bash
python3 -m unittest tests.test_deepseek_llm.DeepSeekLLMTest.test_system_prompt_allows_list_dir_tool
```

Expected: fail because the current prompt only shows `read_file`.

- [ ] **Step 3: Update `_system_prompt()`**

Modify the allowed JSON examples in `src/min_agent/deepseek_llm.py`:

```python
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
  "reason": "Need to inspect available workspace files before choosing context"
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
```

- [ ] **Step 4: Run DeepSeekLLM tests**

Run:

```bash
python3 -m unittest tests.test_deepseek_llm
```

Expected: all DeepSeekLLM tests pass.

Checkpoint: do not commit unless the user explicitly asks for commits during execution.

---

### Task 5: Add V3 Example Workspace Files

**Files:**

- Create: `examples/workspace/project.md`
- Create: `examples/workspace/architecture.md`
- Create: `examples/workspace/usage.md`
- Test: `tests/test_project_structure.py`

- [ ] **Step 1: Add failing structure test**

Add expected files to `tests/test_project_structure.py`:

```python
            "examples/workspace/project.md",
            "examples/workspace/architecture.md",
            "examples/workspace/usage.md",
```

- [ ] **Step 2: Run the structure test and verify it fails**

Run:

```bash
python3 -m unittest tests.test_project_structure.ProjectStructureTest
```

Expected: fail because the files do not exist.

- [ ] **Step 3: Create `project.md`**

Create `examples/workspace/project.md`:

```markdown
# 项目概览

min-agent-demo 是一个可观察的最小 Agent 机制 demo。

它的目标不是复刻 Claude Code，而是展示 Agent 如何在目标、上下文、模型判断、工具调用和观察结果之间循环。
```

- [ ] **Step 4: Create `architecture.md`**

Create `examples/workspace/architecture.md`:

```markdown
# 架构说明

AgentLoop 负责任务循环。

DecisionModel 负责判断下一步动作。

ToolRegistry 负责注册和调用本地工具。

TraceRecorder 负责记录每一步事件，Trace Viewer 负责只读展示事件。
```

- [ ] **Step 5: Create `usage.md`**

Create `examples/workspace/usage.md`:

```markdown
# 使用方式

用户通过 CLI 输入自然语言目标。

默认 fake 模式可以离线运行。

DeepSeek 模式会让真实模型参与下一步判断，但工具执行仍在本地完成。
```

- [ ] **Step 6: Run structure test**

Run:

```bash
python3 -m unittest tests.test_project_structure.ProjectStructureTest
```

Expected: pass.

Checkpoint: do not commit unless the user explicitly asks for commits during execution.

---

### Task 6: Verify AgentLoop V3 End-To-End In Fake Mode

**Files:**

- Test: `tests/test_agent_loop.py`

- [ ] **Step 1: Add failing end-to-end test for discovery then multiple reads**

Add to `tests/test_agent_loop.py`:

```python
    def test_loop_can_discover_and_read_multiple_workspace_files(self) -> None:
        from min_agent.agent_loop import AgentLoop
        from min_agent.context_builder import ContextBuilder
        from min_agent.fake_llm import FakeLLM
        from min_agent.tool_registry import ToolRegistry
        from min_agent.tools.workspace import list_dir, read_file
        from min_agent.trace_recorder import TraceRecorder
        from min_agent.types import ToolSpec

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "project.md").write_text("# 项目\nAgent demo", encoding="utf-8")
            (workspace / "architecture.md").write_text("# 架构\nAgentLoop", encoding="utf-8")

            registry = ToolRegistry()
            registry.register(
                ToolSpec(name="read_file", description="Read file", args_schema={"path": "string"}),
                lambda args: read_file(workspace, args),
            )
            registry.register(
                ToolSpec(name="list_dir", description="List directory", args_schema={"path": "string"}),
                lambda args: list_dir(workspace, args),
            )
            recorder = TraceRecorder(user_goal="请总结这个工作区", workspace=str(workspace))
            loop = AgentLoop(
                context_builder=ContextBuilder(),
                llm=FakeLLM(),
                tools=registry,
                recorder=recorder,
                workspace=str(workspace),
                step_delay_seconds=0,
            )

            result = loop.run("请总结这个工作区")

        self.assertTrue(result.success)
        self.assertIn("project.md", result.message)
        self.assertIn("architecture.md", result.message)
        phases = [event.phase for event in recorder.history()]
        self.assertIn("tool_started", phases)
        tool_names = [
            event.input.get("tool_name")
            for event in recorder.history()
            if event.phase == "tool_started"
        ]
        self.assertIn("list_dir", tool_names)
        self.assertIn("read_file", tool_names)
```

Ensure imports at the top include:

```python
import tempfile
from pathlib import Path
```

- [ ] **Step 2: Run the test and verify it passes only after Tasks 1-3**

Run:

```bash
python3 -m unittest tests.test_agent_loop.AgentLoopTest.test_loop_can_discover_and_read_multiple_workspace_files
```

Expected: pass after `list_dir`, CLI-style registration behavior, and FakeLLM V3 logic exist.

- [ ] **Step 3: Run AgentLoop tests**

Run:

```bash
python3 -m unittest tests.test_agent_loop
```

Expected: all AgentLoop tests pass.

Checkpoint: do not commit unless the user explicitly asks for commits during execution.

---

### Task 7: Update Documentation And Version Records

**Files:**

- Modify: `AGENTS.md`
- Modify: `CHANGELOG.md`
- Modify: `README.md`
- Modify: `docs/runbook.md`

- [ ] **Step 1: Update `AGENTS.md` with V3 boundary**

Add after the V2 boundary:

```markdown
## 第三版边界

第三版在第二版基础上只增加：

- `list_dir` 只读目录工具
- Agent 根据目录列表选择相关 Markdown 文件
- 多文件读取和综合回答

第三版仍然不做：

- 写 workspace 文件
- 运行命令
- 页面控制 Agent
- 长期记忆
- MCP、Hook、插件系统
- 多 Agent

## 第三版安全规则

- `list_dir` 和 `read_file` 都只能访问指定 workspace 内路径。
- `list_dir` 不递归扫描目录。
- `list_dir` 不暴露 workspace 外 symlink 目标。
- DeepSeek 只能返回 `list_dir`、`read_file` 或 `final_answer` 类型的本地 `AgentAction` JSON。
- 工具执行仍必须通过 `ToolRegistry`。
```

- [ ] **Step 2: Update `CHANGELOG.md` V3 section**

Replace the V3 candidate section with a completed V3 section near the top when implementation is done:

```markdown
## V3 - 多文件上下文读取

状态：已完成

这一版解决什么问题：

V2 已经可以让真实模型判断下一步，但上下文仍主要来自单个文件。V3 让 Agent 可以先查看 workspace 目录，再选择相关 Markdown 文件读取并综合回答。

使用者能感受到什么：

- 可以让 Agent 总结整个示例工作区，而不必指定单个文件。
- 观察窗口能看到 Agent 先查看目录，再读取多个文件。
- FakeLLM 模式仍可离线演示多文件上下文流程。
- DeepSeek 模式可以在 `list_dir` 和 `read_file` 之间选择下一步。

这一版不会做什么：

- 不会让 Agent 修改文件。
- 不会让 Agent 执行命令。
- 不会引入长期记忆。
- 不会让网页控制 Agent。

怎么判断这一版完成：

- `list_dir` 能安全列出 workspace 内目录。
- FakeLLM 可以在未指定文件名时完成目录发现、多文件读取和综合回答。
- DeepSeek prompt 允许模型选择 `list_dir` 和 `read_file`。
- 所有测试通过。
```

Keep the later V4-V9 candidate sections below it.

- [ ] **Step 3: Update `README.md` V3 usage**

Add:

````markdown
## V3: 多文件上下文读取

V3 可以让 Agent 先查看 workspace 目录，再选择相关 Markdown 文件读取并综合回答。

运行：

```bash
PYTHONPATH=src python3 -m min_agent.cli \
  "请阅读这个工作区里的资料，并总结这个 demo 是怎么工作的" \
  --workspace examples/workspace
```

这一版仍然只读 workspace 文件，不写文件，不运行命令。
````

- [ ] **Step 4: Update `docs/runbook.md` V3 section**

Add:

````markdown
## V3 多文件上下文演示

运行：

```bash
PYTHONPATH=src python3 -m min_agent.cli \
  "请阅读这个工作区里的资料，并总结这个 demo 是怎么工作的" \
  --workspace examples/workspace
```

预期观察路径：

```text
list_dir -> read_file -> read_file -> final_answer
```

如果目录中没有 Markdown 文件，Agent 应输出可理解的失败说明，而不是崩溃。
````

- [ ] **Step 5: Run documentation consistency search**

Run:

```bash
rg -n "V3|list_dir|多文件|写 workspace|运行命令" AGENTS.md CHANGELOG.md README.md docs/runbook.md src/min_agent tests
```

Expected: V3 references consistently say read-only, no write files, no command execution.

Checkpoint: do not commit unless the user explicitly asks for commits during execution.

---

### Task 8: Full Verification

**Files:**

- No file changes unless verification finds a bug.

- [ ] **Step 1: Run whitespace/conflict check**

Run:

```bash
git diff --check
```

Expected: no output and exit code `0`.

- [ ] **Step 2: Run full test suite**

Run:

```bash
python3 -m unittest discover -s tests
```

Expected: all tests pass.

If sandbox blocks TraceServer tests with `Operation not permitted`, rerun the exact command with approval for local port binding and record that the sandbox failure was caused by localhost binding.

- [ ] **Step 3: Run fake-mode V3 smoke test without browser**

Run:

```bash
PYTHONPATH=src python3 -m min_agent.cli \
  "请阅读这个工作区里的资料，并总结这个 demo 是怎么工作的" \
  --workspace examples/workspace \
  --no-viewer \
  --no-browser \
  --step-delay 0
```

Expected:

- Exit code `0`.
- Output includes a final answer mentioning multiple demo files.
- A run record path is printed.

- [ ] **Step 4: Inspect latest run record for V3 phases**

Open the run record printed in Step 3 and verify:

```text
tool_started list_dir
tool_finished list_dir
tool_started read_file
tool_finished read_file
final_answer
```

Do not commit generated `runs/*.json`; they should remain ignored.

- [ ] **Step 5: Final status check**

Run:

```bash
git status --short
```

Expected: only intentional source, test, doc, and example workspace files are modified or added.

Checkpoint: do not commit unless the user explicitly asks for commits during execution.

---

## 4. Self-Review Checklist

- V3 maps to Agent modules as follows:
  - Goal: unchanged CLI input.
  - Context: stronger workspace context from directory listing.
  - Model / Reasoning: FakeLLM and DeepSeek choose `list_dir`, `read_file`, or `final_answer`.
  - Tools: add `list_dir`; keep `read_file`.
  - Agent Loop: unchanged generic observation loop.
  - Permission: still only safe read boundaries, no approval workflow.
  - Memory / State: single-run observations only.
  - Extension: not implemented.
- No task writes files from the Agent runtime.
- No task runs shell commands from the Agent runtime.
- `AgentLoop` remains generic and does not hardcode V3 steps.
- Tool execution remains local through `ToolRegistry`.
- `TraceEvent` structure remains unchanged.
- Tests are written before implementation in each task.
- Generated run records remain ignored and out of commits.

---

## 5. Execution Handoff

Plan complete. Recommended execution mode:

1. Use subagent-driven development for Tasks 1-7, one task at a time.
2. Review diffs after each task.
3. Run Task 8 verification before claiming V3 complete.
4. Commit only after user confirmation, following the project rule in `AGENTS.md`.
