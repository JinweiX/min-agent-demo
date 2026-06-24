# Min Agent Demo V0.2 DeepSeek Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a DeepSeek-backed real decision model while preserving the V0.1 AgentLoop, ToolRegistry, workspace safety, Trace Viewer, and fake-model fallback.

**Architecture:** V0.2 keeps tool execution local. DeepSeek only returns a structured local `AgentAction` JSON object; `AgentLoop` still decides how to route that action, and all tools still execute through `ToolRegistry`. The default mode remains `FakeLLM`; DeepSeek is opt-in through CLI flags and reads its API key only from `DEEPSEEK_API_KEY`.

**Tech Stack:** Python 3.10+ standard library, `urllib.request`, `json`, `unittest`, DeepSeek OpenAI-compatible Chat Completions API, DeepSeek JSON Output (`response_format={"type":"json_object"}`), vanilla existing Trace Viewer.

---

## 0. Scope And Non-Goals

### In Scope

- `DecisionModel` protocol for replaceable decision engines.
- `DeepSeekClient` for non-streaming OpenAI-compatible chat completions.
- `DeepSeekLLM` that converts `AgentContext` into a DeepSeek prompt and parses JSON into `AgentAction`.
- CLI switch between `fake` and `deepseek`.
- `DEEPSEEK_API_KEY` startup validation only when DeepSeek mode is selected.
- Robust model-failure convergence: request failures, HTTP errors, empty content, malformed responses, invalid JSON, and invalid actions must become observable Agent failures instead of uncaught crashes.
- Documentation for V0.1/V0.2 comparison and DeepSeek usage.
- Unit tests with fake HTTP openers; no real DeepSeek requests in tests.

### Out Of Scope

- OpenAI Responses API.
- DeepSeek function calling / tool calls.
- Anthropic-compatible DeepSeek API.
- Streaming model output.
- Writing workspace files.
- Running shell commands as an Agent tool.
- Frontend Agent control.
- `.env` creation or loading.
- Saving or printing API keys.
- More tools, MCP, hooks, memory, or multi-agent behavior.

### Official API Facts Used

- DeepSeek supports an OpenAI-compatible API format with `base_url` `https://api.deepseek.com`.
- The non-streaming chat API is `/chat/completions`.
- DeepSeek JSON Output requires `response_format={"type":"json_object"}` and the prompt should include the word `json` plus an example JSON output.
- DeepSeek docs warn JSON Output may occasionally return empty content; V0.2 must handle empty content.
- Current DeepSeek docs list `deepseek-v4-flash` and `deepseek-v4-pro`; V0.2 defaults to `deepseek-v4-flash`.

References:

- <https://api-docs.deepseek.com/>
- <https://api-docs.deepseek.com/guides/json_mode>
- <https://api-docs.deepseek.com/guides/function_calling>

---

## 1. Target File Structure

Create:

```text
src/min_agent/
  decision_model.py
  deepseek_client.py
  deepseek_llm.py

tests/
  test_decision_model.py
  test_deepseek_client.py
  test_deepseek_llm.py
```

Modify:

```text
AGENTS.md
CHANGELOG.md
README.md
docs/runbook.md
src/min_agent/agent_loop.py
src/min_agent/cli.py
tests/test_agent_loop.py
tests/test_cli.py
tests/test_project_structure.py
```

Do not modify as part of this plan unless explicitly needed:

```text
examples/workspace/notes.md
```

The user has confirmed the current uncommitted `examples/workspace/notes.md` change should be preserved. Do not revert it.

---

## 2. Behavioral Design

### CLI Modes

Default remains V0.1 fake mode:

```bash
PYTHONPATH=src python3 -m min_agent.cli "请读取 notes.md 并总结" --workspace examples/workspace
```

DeepSeek mode:

```bash
DEEPSEEK_API_KEY=... PYTHONPATH=src python3 -m min_agent.cli \
  "请读取 notes.md 并总结" \
  --workspace examples/workspace \
  --decision-model deepseek \
  --deepseek-model deepseek-v4-flash
```

New CLI args:

```text
--decision-model fake|deepseek
--deepseek-model deepseek-v4-flash
--deepseek-base-url https://api.deepseek.com
--model-max-tokens 1200
```

Rules:

- `--decision-model fake` must not read or require `DEEPSEEK_API_KEY`.
- `--decision-model deepseek` requires `DEEPSEEK_API_KEY`.
- Missing key returns `2`.
- Startup/config errors return `2`.
- Agent task failures still return `0` when handled gracefully and recorded.

### DeepSeek Action JSON Contract

DeepSeek must return one of these local action objects.

Tool call:

```json
{
  "kind": "tool_call",
  "tool_name": "read_file",
  "args": {"path": "notes.md"},
  "reason": "需要读取文件内容后才能总结"
}
```

Final answer:

```json
{
  "kind": "final_answer",
  "message": "notes.md 的主要内容是...",
  "reason": "已经获得文件内容",
  "success": true
}
```

Invalid model output must not crash the CLI. It must produce:

```python
AgentAction.final_answer(
    message="模型返回了无法解析的决策 JSON。",
    reason="模型输出不是合法 AgentAction",
    success=False,
)
```

Request failures must produce:

```python
AgentAction.final_answer(
    message="模型调用失败：<safe error message>",
    reason="DeepSeek 请求失败",
    success=False,
)
```

Safe error messages must not include `DEEPSEEK_API_KEY`.

---

## 3. Implementation Tasks

### Task 1: Update V0.2 Project Rules

**Files:**
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `docs/runbook.md`

- [ ] **Step 1: Update `AGENTS.md` before implementation**

Add a V0.2 section after the V0.1 scope:

```markdown
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
```

- [ ] **Step 2: Update README V0.1/V0.2 wording**

Add a short V0.2 section:

```markdown
## V0.2: DeepSeek 决策器

V0.2 可以把默认的 `FakeLLM` 替换为 DeepSeek 真实模型决策器，但工具执行仍由本地 `ToolRegistry` 控制。

DeepSeek 模式使用环境变量：

```bash
export DEEPSEEK_API_KEY=...
```

运行：

```bash
PYTHONPATH=src python3 -m min_agent.cli "请读取 notes.md 并总结" \
  --workspace examples/workspace \
  --decision-model deepseek \
  --deepseek-model deepseek-v4-flash
```
```

- [ ] **Step 3: Update runbook troubleshooting**

Add:

```markdown
### DeepSeek key 缺失

当使用 `--decision-model deepseek` 时，必须设置 `DEEPSEEK_API_KEY`。

缺失时 CLI 返回 `2`。

### DeepSeek 请求失败

模型请求失败属于 Agent 任务失败。程序不应崩溃，应保存 run record，最终回答中说明模型调用失败。

### 回退到 FakeLLM

如果 DeepSeek API 不可用，使用默认 fake 模式：

```bash
PYTHONPATH=src python3 -m min_agent.cli "请读取 notes.md 并总结" --workspace examples/workspace
```
```

- [ ] **Step 4: Verify docs-only change does not break tests**

Run:

```bash
python3 -m unittest discover -s tests
```

Expected: all tests pass.

---

### Task 2: Add `DecisionModel` Protocol

**Files:**
- Create: `src/min_agent/decision_model.py`
- Create: `tests/test_decision_model.py`
- Modify: `src/min_agent/agent_loop.py`
- Modify: `tests/test_project_structure.py`

- [ ] **Step 1: Write failing protocol test**

Create `tests/test_decision_model.py`:

```python
from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class DecisionModelTest(unittest.TestCase):
    def test_fake_llm_satisfies_decision_model_protocol(self) -> None:
        from min_agent.decision_model import DecisionModel
        from min_agent.fake_llm import FakeLLM

        model: DecisionModel = FakeLLM()

        self.assertTrue(hasattr(model, "decide"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run failing test**

Run:

```bash
python3 -m unittest tests.test_decision_model
```

Expected before implementation: import failure for `min_agent.decision_model`.

- [ ] **Step 3: Create `decision_model.py`**

Create `src/min_agent/decision_model.py`:

```python
from __future__ import annotations

from typing import Protocol

from min_agent.types import AgentAction, AgentContext


class DecisionModel(Protocol):
    def decide(self, context: AgentContext) -> AgentAction:
        ...
```

- [ ] **Step 4: Type AgentLoop against protocol**

In `src/min_agent/agent_loop.py`, add:

```python
from min_agent.decision_model import DecisionModel
```

Change:

```python
llm: object,
```

to:

```python
llm: DecisionModel,
```

- [ ] **Step 5: Add file to structure test**

Add to `required_paths` in `tests/test_project_structure.py`:

```python
"src/min_agent/decision_model.py",
```

- [ ] **Step 6: Verify**

Run:

```bash
python3 -m unittest tests.test_decision_model
python3 -m unittest tests.test_agent_loop
python3 -m unittest discover -s tests
```

Expected: all tests pass.

---

### Task 3: Add `DeepSeekClient`

**Files:**
- Create: `src/min_agent/deepseek_client.py`
- Create: `tests/test_deepseek_client.py`
- Modify: `tests/test_project_structure.py`

- [ ] **Step 1: Write failing client tests**

Create `tests/test_deepseek_client.py`:

```python
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from urllib.error import HTTPError, URLError


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class FakeResponse:
    def __init__(self, payload: dict | str) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        if isinstance(self.payload, str):
            return self.payload.encode("utf-8")
        return json.dumps(self.payload).encode("utf-8")


class FakeOpener:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.requests = []

    def open(self, request, timeout=30):
        self.requests.append((request, timeout))
        return FakeResponse(self.payload)


class FailingOpener:
    def open(self, request, timeout=30):
        raise HTTPError(
            url=request.full_url,
            code=500,
            msg="server error",
            hdrs={},
            fp=None,
        )


class UrlFailingOpener:
    def open(self, request, timeout=30):
        raise URLError("network down")


class DeepSeekClientTest(unittest.TestCase):
    def test_create_chat_completion_sends_expected_request(self) -> None:
        from min_agent.deepseek_client import DeepSeekClient

        opener = FakeOpener(
            {
                "choices": [
                    {"message": {"content": "{\"kind\":\"final_answer\",\"message\":\"ok\",\"reason\":\"done\",\"success\":true}"}}
                ]
            }
        )
        client = DeepSeekClient(
            api_key="secret-key",
            model="deepseek-v4-flash",
            opener=opener,
            timeout_seconds=7,
            max_tokens=1200,
        )

        content = client.create_chat_completion("system json", "user input")

        request, timeout = opener.requests[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(content, "{\"kind\":\"final_answer\",\"message\":\"ok\",\"reason\":\"done\",\"success\":true}")
        self.assertEqual(timeout, 7)
        self.assertEqual(request.full_url, "https://api.deepseek.com/chat/completions")
        self.assertEqual(request.headers["Authorization"], "Bearer secret-key")
        self.assertEqual(body["model"], "deepseek-v4-flash")
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertEqual(body["max_tokens"], 1200)
        self.assertFalse(body["stream"])

    def test_http_error_raises_safe_client_error(self) -> None:
        from min_agent.deepseek_client import DeepSeekClient, ModelClientError

        client = DeepSeekClient(api_key="secret-key", model="deepseek-v4-flash", opener=FailingOpener())

        with self.assertRaises(ModelClientError) as caught:
            client.create_chat_completion("system json", "user input")

        self.assertIn("HTTP 500", str(caught.exception))
        self.assertNotIn("secret-key", str(caught.exception))

    def test_url_error_raises_safe_client_error(self) -> None:
        from min_agent.deepseek_client import DeepSeekClient, ModelClientError

        client = DeepSeekClient(api_key="secret-key", model="deepseek-v4-flash", opener=UrlFailingOpener())

        with self.assertRaises(ModelClientError) as caught:
            client.create_chat_completion("system json", "user input")

        self.assertIn("DeepSeek request failed", str(caught.exception))
        self.assertNotIn("secret-key", str(caught.exception))

    def test_non_json_response_raises_client_error(self) -> None:
        from min_agent.deepseek_client import DeepSeekClient, ModelClientError

        client = DeepSeekClient(
            api_key="secret-key",
            model="deepseek-v4-flash",
            opener=FakeOpener("not json"),
        )

        with self.assertRaises(ModelClientError) as caught:
            client.create_chat_completion("system json", "user input")

        self.assertIn("not valid JSON", str(caught.exception))

    def test_missing_content_raises_client_error(self) -> None:
        from min_agent.deepseek_client import DeepSeekClient, ModelClientError

        client = DeepSeekClient(
            api_key="secret-key",
            model="deepseek-v4-flash",
            opener=FakeOpener({"choices": [{"message": {}}]}),
        )

        with self.assertRaises(ModelClientError) as caught:
            client.create_chat_completion("system json", "user input")

        self.assertIn("missing message content", str(caught.exception))

    def test_empty_content_raises_client_error(self) -> None:
        from min_agent.deepseek_client import DeepSeekClient, ModelClientError

        client = DeepSeekClient(
            api_key="secret-key",
            model="deepseek-v4-flash",
            opener=FakeOpener({"choices": [{"message": {"content": ""}}]}),
        )

        with self.assertRaises(ModelClientError) as caught:
            client.create_chat_completion("system json", "user input")

        self.assertIn("empty message content", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
python3 -m unittest tests.test_deepseek_client
```

Expected before implementation: import failure for `min_agent.deepseek_client`.

- [ ] **Step 3: Implement `DeepSeekClient`**

Create `src/min_agent/deepseek_client.py`:

```python
from __future__ import annotations

import json
import urllib.request
from typing import Any
from urllib.error import HTTPError, URLError


class ModelClientError(Exception):
    pass


class DeepSeekClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.deepseek.com",
        timeout_seconds: float = 30,
        max_tokens: int = 1200,
        opener: Any | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.opener = opener or urllib.request.build_opener()

    def create_chat_completion(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        request = urllib.request.Request(
            url=f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with self.opener.open(request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise ModelClientError(f"DeepSeek request failed with HTTP {exc.code}") from exc
        except URLError as exc:
            raise ModelClientError(f"DeepSeek request failed: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise ModelClientError("DeepSeek response was not valid JSON") from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelClientError("DeepSeek response missing message content") from exc

        if not isinstance(content, str):
            raise ModelClientError("DeepSeek response message content is not a string")
        if not content.strip():
            raise ModelClientError("DeepSeek response empty message content")
        return content
```

- [ ] **Step 4: Add file to structure test**

Add to `required_paths`:

```python
"src/min_agent/deepseek_client.py",
```

- [ ] **Step 5: Verify**

Run:

```bash
python3 -m unittest tests.test_deepseek_client
python3 -m unittest discover -s tests
```

Expected: all tests pass.

---

### Task 4: Add `DeepSeekLLM`

**Files:**
- Create: `src/min_agent/deepseek_llm.py`
- Create: `tests/test_deepseek_llm.py`
- Modify: `tests/test_project_structure.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_deepseek_llm.py`:

```python
from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class StubClient:
    def __init__(self, content: str | Exception) -> None:
        self.content = content
        self.calls = []

    def create_chat_completion(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        if isinstance(self.content, Exception):
            raise self.content
        return self.content


class DeepSeekLLMTest(unittest.TestCase):
    def test_parses_tool_call(self) -> None:
        from min_agent.deepseek_llm import DeepSeekLLM
        from min_agent.types import AgentContext, ToolSpec

        llm = DeepSeekLLM(
            client=StubClient(
                '{"kind":"tool_call","tool_name":"read_file","args":{"path":"notes.md"},"reason":"需要读取文件"}'
            ),
            model="deepseek-v4-flash",
        )
        context = AgentContext(
            user_goal="请读取 notes.md 并总结",
            workspace="examples/workspace",
            available_tools=[ToolSpec(name="read_file", description="Read file")],
            observations=[],
        )

        action = llm.decide(context)

        self.assertEqual(action.kind, "tool_call")
        self.assertEqual(action.tool_name, "read_file")
        self.assertEqual(action.args, {"path": "notes.md"})

    def test_parses_final_answer(self) -> None:
        from min_agent.deepseek_llm import DeepSeekLLM
        from min_agent.types import AgentContext, ToolSpec

        llm = DeepSeekLLM(
            client=StubClient(
                '{"kind":"final_answer","message":"总结完成","reason":"已有内容","success":true}'
            ),
            model="deepseek-v4-flash",
        )
        context = AgentContext(
            user_goal="请读取 notes.md 并总结",
            workspace="examples/workspace",
            available_tools=[ToolSpec(name="read_file", description="Read file")],
            observations=[],
        )

        action = llm.decide(context)

        self.assertEqual(action.kind, "final_answer")
        self.assertTrue(action.success)
        self.assertEqual(action.message, "总结完成")

    def test_invalid_json_becomes_failed_final_answer(self) -> None:
        from min_agent.deepseek_llm import DeepSeekLLM
        from min_agent.types import AgentContext, ToolSpec

        llm = DeepSeekLLM(client=StubClient("not json"), model="deepseek-v4-flash")
        context = AgentContext(
            user_goal="请读取 notes.md 并总结",
            workspace="examples/workspace",
            available_tools=[ToolSpec(name="read_file", description="Read file")],
            observations=[],
        )

        action = llm.decide(context)

        self.assertEqual(action.kind, "final_answer")
        self.assertFalse(action.success)
        self.assertIn("无法解析", action.message or "")

    def test_unknown_tool_becomes_failed_final_answer(self) -> None:
        from min_agent.deepseek_llm import DeepSeekLLM
        from min_agent.types import AgentContext, ToolSpec

        llm = DeepSeekLLM(
            client=StubClient(
                '{"kind":"tool_call","tool_name":"delete_file","args":{"path":"notes.md"},"reason":"错误工具"}'
            ),
            model="deepseek-v4-flash",
        )
        context = AgentContext(
            user_goal="请读取 notes.md 并总结",
            workspace="examples/workspace",
            available_tools=[ToolSpec(name="read_file", description="Read file")],
            observations=[],
        )

        action = llm.decide(context)

        self.assertEqual(action.kind, "final_answer")
        self.assertFalse(action.success)
        self.assertIn("不可用工具", action.message or "")

    def test_client_error_becomes_failed_final_answer(self) -> None:
        from min_agent.deepseek_client import ModelClientError
        from min_agent.deepseek_llm import DeepSeekLLM
        from min_agent.types import AgentContext, ToolSpec

        llm = DeepSeekLLM(
            client=StubClient(ModelClientError("DeepSeek request failed with HTTP 500")),
            model="deepseek-v4-flash",
        )
        context = AgentContext(
            user_goal="请读取 notes.md 并总结",
            workspace="examples/workspace",
            available_tools=[ToolSpec(name="read_file", description="Read file")],
            observations=[],
        )

        action = llm.decide(context)

        self.assertEqual(action.kind, "final_answer")
        self.assertFalse(action.success)
        self.assertIn("模型调用失败", action.message or "")

    def test_prompt_mentions_json_and_action_schema(self) -> None:
        from min_agent.deepseek_llm import DeepSeekLLM
        from min_agent.types import AgentContext, ToolSpec

        client = StubClient(
            '{"kind":"final_answer","message":"ok","reason":"done","success":true}'
        )
        llm = DeepSeekLLM(client=client, model="deepseek-v4-flash")
        context = AgentContext(
            user_goal="请读取 notes.md 并总结",
            workspace="examples/workspace",
            available_tools=[ToolSpec(name="read_file", description="Read file")],
            observations=[],
        )

        llm.decide(context)

        system_prompt, user_prompt = client.calls[0]
        # DeepSeek JSON Output requires the prompt to include "json" and an output example.
        self.assertIn("json", system_prompt.lower())
        self.assertIn("AgentAction", system_prompt)
        self.assertIn("available_tools", user_prompt)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
python3 -m unittest tests.test_deepseek_llm
```

Expected before implementation: import failure for `min_agent.deepseek_llm`.

- [ ] **Step 3: Implement `DeepSeekLLM`**

Create `src/min_agent/deepseek_llm.py`:

```python
from __future__ import annotations

import json
from typing import Protocol

from min_agent.deepseek_client import ModelClientError
from min_agent.types import AgentAction, AgentContext


class ChatCompletionClient(Protocol):
    def create_chat_completion(self, system_prompt: str, user_prompt: str) -> str:
        ...


class DeepSeekLLM:
    def __init__(self, client: ChatCompletionClient, model: str) -> None:
        self.client = client
        self.model = model

    def decide(self, context: AgentContext) -> AgentAction:
        try:
            raw_content = self.client.create_chat_completion(
                system_prompt=self._system_prompt(),
                user_prompt=self._user_prompt(context),
            )
        except ModelClientError as exc:
            return AgentAction.final_answer(
                message=f"模型调用失败：{exc}",
                reason="DeepSeek 请求失败",
                success=False,
            )

        try:
            data = json.loads(raw_content)
        except json.JSONDecodeError:
            return self._invalid_action("模型返回了无法解析的决策 JSON。", "模型输出不是合法 JSON")

        return self._action_from_data(data, context)

    def _action_from_data(self, data: object, context: AgentContext) -> AgentAction:
        if not isinstance(data, dict):
            return self._invalid_action("模型返回了无法解析的决策 JSON。", "模型输出不是 JSON object")

        kind = data.get("kind")
        reason = data.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            reason = "模型没有提供有效 reason"

        if kind == "tool_call":
            tool_name = data.get("tool_name")
            args = data.get("args")
            if not isinstance(tool_name, str) or not tool_name:
                return self._invalid_action("模型返回的工具调用缺少 tool_name。", reason)
            if tool_name not in {tool.name for tool in context.available_tools}:
                return self._invalid_action(f"模型请求了不可用工具：{tool_name}", reason)
            if not isinstance(args, dict):
                return self._invalid_action("模型返回的工具调用缺少 args。", reason)
            return AgentAction.tool_call(tool_name=tool_name, args=args, reason=reason)

        if kind == "final_answer":
            message = data.get("message")
            success = data.get("success", True)
            if not isinstance(message, str):
                return self._invalid_action("模型返回的最终回答缺少 message。", reason)
            if not isinstance(success, bool):
                return self._invalid_action("模型返回的 success 不是布尔值。", reason)
            return AgentAction.final_answer(message=message, reason=reason, success=success)

        return self._invalid_action("模型返回了未知的决策类型。", reason)

    def _invalid_action(self, message: str, reason: str) -> AgentAction:
        return AgentAction.final_answer(message=message, reason=reason, success=False)

    def _system_prompt(self) -> str:
        return """You are the decision model for min-agent-demo.
Return only one valid json object matching the local AgentAction schema.
Do not use markdown fences.
Do not invent tools.

Allowed json outputs:
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

    def _user_prompt(self, context: AgentContext) -> str:
        return json.dumps(
            {
                "model": self.model,
                "user_goal": context.user_goal,
                "workspace": context.workspace,
                "available_tools": [tool.to_dict() for tool in context.available_tools],
                "observations": [observation.to_dict() for observation in context.observations],
            },
            ensure_ascii=False,
            indent=2,
        )
```

- [ ] **Step 4: Add file to structure test**

Add to `required_paths`:

```python
"src/min_agent/deepseek_llm.py",
```

- [ ] **Step 5: Verify**

Run:

```bash
python3 -m unittest tests.test_deepseek_llm
python3 -m unittest discover -s tests
```

Expected: all tests pass.

---

### Task 5: Wire DeepSeek Into CLI

**Files:**
- Modify: `src/min_agent/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Append to `tests/test_cli.py`:

```python
    def test_cli_default_fake_mode_does_not_require_deepseek_key(self) -> None:
        from min_agent.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            runs = root / "runs"
            workspace.mkdir()
            (workspace / "notes.md").write_text("# 示例", encoding="utf-8")

            with patch.dict("os.environ", {}, clear=True):
                exit_code = main(
                    [
                        "请读取 notes.md 并总结",
                        "--workspace",
                        str(workspace),
                        "--runs-dir",
                        str(runs),
                        "--no-viewer",
                        "--no-browser",
                        "--step-delay",
                        "0",
                    ]
                )

        self.assertEqual(exit_code, 0)

    def test_cli_deepseek_mode_requires_key(self) -> None:
        from min_agent.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            (workspace / "notes.md").write_text("# 示例", encoding="utf-8")

            with patch.dict("os.environ", {}, clear=True):
                exit_code = main(
                    [
                        "请读取 notes.md 并总结",
                        "--workspace",
                        str(workspace),
                        "--decision-model",
                        "deepseek",
                        "--no-viewer",
                        "--no-browser",
                    ]
                )

        self.assertEqual(exit_code, 2)
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
python3 -m unittest tests.test_cli
```

Expected before implementation: argument parsing failure for `--decision-model`.

- [ ] **Step 3: Add CLI arguments**

In `build_parser()` add:

```python
    parser.add_argument(
        "--decision-model",
        choices=["fake", "deepseek"],
        default="fake",
        help="Decision model backend.",
    )
    parser.add_argument("--deepseek-model", default="deepseek-v4-flash", help="DeepSeek model name.")
    parser.add_argument("--deepseek-base-url", default="https://api.deepseek.com", help="DeepSeek OpenAI-compatible base URL.")
    parser.add_argument("--model-max-tokens", type=int, default=1200, help="Maximum model output tokens.")
```

- [ ] **Step 4: Add model factory in CLI**

In `src/min_agent/cli.py`, import:

```python
import os

from min_agent.deepseek_client import DeepSeekClient
from min_agent.deepseek_llm import DeepSeekLLM
```

Add helper:

```python
def build_decision_model(args: argparse.Namespace):
    if args.decision_model == "fake":
        return FakeLLM(), None

    if args.decision_model == "deepseek":
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            return None, "DEEPSEEK_API_KEY is required when --decision-model deepseek"

        client = DeepSeekClient(
            api_key=api_key,
            model=args.deepseek_model,
            base_url=args.deepseek_base_url,
            max_tokens=args.model_max_tokens,
        )
        return DeepSeekLLM(client=client, model=args.deepseek_model), None

    return None, f"Unknown decision model: {args.decision_model}"
```

In `main()`, call `build_decision_model(args)` after workspace validation and before starting Trace Viewer. Missing `DEEPSEEK_API_KEY` must return `2` before any viewer/server/browser side effect.

```python
    llm, model_error = build_decision_model(args)
    if model_error is not None:
        print(f"Error: {model_error}")
        return 2
```

Then, when constructing `AgentLoop`, replace `FakeLLM()` with:

```python
llm=llm,
```

- [ ] **Step 5: Verify**

Run:

```bash
python3 -m unittest tests.test_cli
python3 -m unittest discover -s tests
```

Expected: all tests pass.

---

### Task 6: Verify AgentLoop Still Owns Tool Execution

**Files:**
- Modify: `tests/test_agent_loop.py`

- [ ] **Step 1: Add regression test**

Add to `tests/test_agent_loop.py`:

```python
    def test_loop_uses_registry_for_model_tool_call(self) -> None:
        from min_agent.agent_loop import AgentLoop
        from min_agent.context_builder import ContextBuilder
        from min_agent.tool_registry import ToolRegistry
        from min_agent.trace_recorder import TraceRecorder
        from min_agent.types import AgentAction, AgentContext, ToolResult, ToolSpec

        class ToolCallModel:
            def __init__(self) -> None:
                self.calls = 0

            def decide(self, context: AgentContext) -> AgentAction:
                self.calls += 1
                if self.calls == 1:
                    return AgentAction.tool_call("registered_tool", {}, "需要调用注册工具")
                return AgentAction.final_answer("done", "工具已调用")

        registry = ToolRegistry()
        calls = []
        registry.register(
            ToolSpec(name="registered_tool", description="Registered test tool"),
            lambda args: calls.append(args) or ToolResult(success=True, content="ok"),
        )
        recorder = TraceRecorder(user_goal="goal", workspace="workspace")
        loop = AgentLoop(
            context_builder=ContextBuilder(),
            llm=ToolCallModel(),
            tools=registry,
            recorder=recorder,
            workspace="workspace",
            step_delay_seconds=0,
        )

        result = loop.run("goal")

        self.assertTrue(result.success)
        self.assertEqual(calls, [{}])
```

- [ ] **Step 2: Verify**

Run:

```bash
python3 -m unittest tests.test_agent_loop
python3 -m unittest discover -s tests
```

Expected: all tests pass.

---

### Task 7: Documentation Finalization

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `README.md`
- Modify: `docs/runbook.md`

- [ ] **Step 1: README commands**

Ensure README contains these exact command examples:

```bash
PYTHONPATH=src python3 -m min_agent.cli "请读取 notes.md 并总结" --workspace examples/workspace
```

```bash
DEEPSEEK_API_KEY=... PYTHONPATH=src python3 -m min_agent.cli \
  "请读取 notes.md 并总结" \
  --workspace examples/workspace \
  --decision-model deepseek \
  --deepseek-model deepseek-v4-flash
```

- [ ] **Step 2: Update product changelog**

In `CHANGELOG.md`, update the V0.2 entry during implementation completion:

```markdown
## V0.2 - 接入真实模型判断能力

状态：已完成

这一版解决什么问题：

V0.1 只能用预设规则演示 Agent 判断。V0.2 接入 DeepSeek，让 Agent 可以由真实模型判断下一步，同时保留本地工具边界。

使用者能感受到什么：

- 可以选择使用真实模型参与 Agent 决策。
- 默认 FakeLLM 模式仍可离线运行。
- 观察窗口仍能看到 Agent 每一步。
- 模型调用失败时，系统会给出可理解的失败说明，而不是崩溃。
```

- [ ] **Step 3: Runbook troubleshooting**

Ensure runbook documents:

- missing `DEEPSEEK_API_KEY`
- DeepSeek HTTP failure
- empty content from JSON Output
- invalid model JSON
- fallback to fake mode
- API key is never written into `.env`, code, TraceEvent, or run record

- [ ] **Step 4: Verify docs commands remain consistent**

Run:

```bash
rg -n "DEEPSEEK_API_KEY|decision-model|deepseek-v4-flash|deepseek-base-url" README.md docs/runbook.md AGENTS.md src/min_agent tests
```

Expected: references are consistent and no `.env` instruction is introduced.

---

### Task 8: Final Verification

**Files:**
- No new files.

- [ ] **Step 1: Run full tests**

Run:

```bash
python3 -m unittest discover -s tests
```

Expected: all tests pass.

- [ ] **Step 2: Verify fake mode still works without key**

Run:

```bash
env -u DEEPSEEK_API_KEY PYTHONPATH=src python3 -m min_agent.cli \
  "请读取 notes.md 并总结" \
  --workspace examples/workspace \
  --no-viewer \
  --no-browser \
  --step-delay 0
```

Expected:

- exit code `0`
- output includes `notes.md`
- run record is saved

- [ ] **Step 3: Verify missing key path**

Run:

```bash
env -u DEEPSEEK_API_KEY PYTHONPATH=src python3 -m min_agent.cli \
  "请读取 notes.md 并总结" \
  --workspace examples/workspace \
  --decision-model deepseek \
  --no-viewer \
  --no-browser
```

Expected:

- exit code `2`
- output includes `DEEPSEEK_API_KEY is required`
- no API request is attempted

- [ ] **Step 4: Optional manual DeepSeek verification**

Only run when the user has `DEEPSEEK_API_KEY` available in the shell:

```bash
DEEPSEEK_API_KEY=... PYTHONPATH=src python3 -m min_agent.cli \
  "请读取 notes.md 并总结" \
  --workspace examples/workspace \
  --decision-model deepseek \
  --deepseek-model deepseek-v4-flash \
  --no-viewer \
  --no-browser \
  --step-delay 0
```

Expected:

- exit code `0`
- DeepSeek decides to call `read_file` or produces a safe final answer
- tool execution still goes through `ToolRegistry`
- run record is saved
- no API key appears in output or run record

---

## 4. Review Checklist

Before implementation is considered complete:

- [ ] `fake` remains the default decision model.
- [ ] `fake` mode never requires `DEEPSEEK_API_KEY`.
- [ ] `deepseek` mode requires `DEEPSEEK_API_KEY`.
- [ ] API key is not written to code, docs examples, TraceEvent, or run records.
- [ ] DeepSeek uses OpenAI-compatible chat completions, not Responses API.
- [ ] DeepSeek JSON Output uses `response_format={"type":"json_object"}`.
- [ ] Prompt includes `json` and concrete AgentAction JSON examples.
- [ ] Request failures, HTTP errors, invalid response shapes, empty content, invalid JSON, and invalid action objects become observable failed final answers.
- [ ] `DeepSeekLLM` rejects unavailable tools before `AgentLoop` calls `ToolRegistry`.
- [ ] `AgentLoop` still only executes tools through `ToolRegistry`.
- [ ] Workspace path safety remains unchanged.
- [ ] No `.env` file is created.
- [ ] No new runtime dependency is introduced.
- [ ] `python3 -m unittest discover -s tests` passes.

---

## 5. Execution Notes

- Current branch should be `codex/min-agent-demo-v0.2`.
- V0.1 is preserved at tag `v1`.
- The user confirmed the current `examples/workspace/notes.md` modification should be preserved.
- Do not commit unless the user explicitly confirms.
- Do not push.
