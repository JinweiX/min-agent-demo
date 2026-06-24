# Min Agent Demo V0.4 Trace Viewer Explainability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the Trace Viewer so a product reviewer can understand each Agentic Loop round, the original request, the final answer, and the explainable input/output of every step without changing Agent runtime behavior.

**Architecture:** V0.4 is a viewer-only explainability iteration. The Python Agent loop, trace recorder, trace server, tool registry, workspace tools, FakeLLM, DeepSeekLLM, and CLI behavior must remain unchanged unless a test proves a viewer contract cannot be met from the existing `TraceEvent` data. The frontend stays vanilla HTML/CSS/JS and derives all round, summary, and detail views from the existing event stream.

**Tech Stack:** Python 3.10+ `unittest`, existing `TraceEvent` JSON stream, vanilla `web/trace_viewer.html`, `web/trace_viewer.css`, and `web/trace_viewer.js`; no frontend framework, no external assets, no new dependencies.

---

## 0. Scope And Non-Goals

### In Scope

- Replace the current flat left-side event list with Agentic Loop round grouping.
- Keep ordered step display inside each selected round.
- Show explainable input and output for every step.
- Show model decision details clearly:
  - FakeLLM: state that no real model was called, then show the parsed local `AgentAction`.
  - DeepSeek: show `System Prompt`, `User Prompt`, returned `message.content`, and parsed local `AgentAction`.
- Add top run statistics:
  - total Agentic Loop rounds
  - model decisions
  - `list_dir` calls
  - `read_file` calls
  - observations added
- Add a dedicated original request module.
- Put modules in this order:
  - status header
  - run statistics
  - original request
  - final result
  - observation window: left round list, right round details
- Preserve the Trace Viewer as a read-only observation window.
- Update tests and docs so the intended V0.4 behavior is locked down.

### Out Of Scope

- Changing Agent execution logic.
- Changing `TraceEvent` schema.
- Changing run record format.
- Changing SSE protocol or trace server routing.
- Adding Agent controls in the page.
- Adding pause, resume, retry, edit goal, or rerun actions.
- Adding frontend framework, build step, external CSS, external font, or icon library.
- Changing tool security behavior.
- Changing DeepSeek prompt, JSON contract, model client, API key handling, or CLI flags.
- Redesigning the page into a dark console, dashboard, landing page, or decorative visual demo.

### Product Boundary

V0.4 should make this path understandable:

```text
Original request
-> Round 1: build context -> model decision -> tool call -> observation
-> Round 2: build context -> model decision -> tool call -> observation
-> Round N: build context -> model decision -> final answer
-> Final result
```

The page should answer three reviewer questions:

1. This run executed how many rounds and tool/model steps?
2. In each round, what did the Agent know, decide, do, and observe?
3. For a model decision, what content was sent to the model and what did the model return?

---

## 1. File Boundaries

### Allowed Files

Modify only these files unless a listed test proves an unavoidable issue:

```text
web/trace_viewer.html
web/trace_viewer.css
web/trace_viewer.js
tests/test_trace_viewer_source.py
AGENTS.md
CHANGELOG.md
README.md
docs/runbook.md
```

### Forbidden Files

Do not modify these files for V0.4:

```text
src/min_agent/agent_loop.py
src/min_agent/cli.py
src/min_agent/context_builder.py
src/min_agent/decision_model.py
src/min_agent/deepseek_client.py
src/min_agent/deepseek_llm.py
src/min_agent/fake_llm.py
src/min_agent/tool_registry.py
src/min_agent/trace_recorder.py
src/min_agent/trace_server.py
src/min_agent/types.py
src/min_agent/tools/workspace.py
tests/test_agent_loop.py
tests/test_cli.py
tests/test_context_builder.py
tests/test_deepseek_client.py
tests/test_deepseek_llm.py
tests/test_decision_model.py
tests/test_fake_llm.py
tests/test_tool_registry.py
tests/test_trace_recorder.py
tests/test_trace_server.py
tests/test_types.py
tests/test_workspace_tools.py
```

### Why This Boundary Exists

Current `TraceEvent` already contains enough information:

- `run_started.input.user_goal`
- `context_built.output`
- `llm_decision.output.metadata.model_call`
- `tool_started.input`
- `tool_finished.output`
- `observation_added.output`
- `final_answer.output.message`

V0.4 should reorganize and explain existing data. It must not change how the Agent works.

---

## 2. Target Page Structure

Update `web/trace_viewer.html` to use this conceptual structure:

```html
<main class="shell">
  <header class="status">...</header>

  <section class="run-summary" aria-label="Run summary">
    <div id="run-summary" class="run-summary-grid"></div>
  </section>

  <section class="original-request">
    <h2>原始需求</h2>
    <p id="original-request">等待任务开始。</p>
  </section>

  <section class="result">
    <h2>最终结果</h2>
    <p id="final-answer">任务完成后展示最终回答。</p>
  </section>

  <section class="layout" aria-label="Agentic loop trace">
    <ol id="round-list" class="round-list"></ol>
    <aside class="detail">
      <h2>轮次详情</h2>
      <div id="round-detail" class="round-detail">暂无事件。</div>
    </aside>
  </section>
</main>
```

Important:

- The original request must be above the final result.
- The final result must be above the observation window.
- The observation window must still show both overview and details.
- The old `#timeline` and `#step-detail` containers should be removed or replaced, not left as unused duplicate UI.
- Do not add external scripts, CDN links, images, fonts, or framework files.

---

## 3. Round Grouping Rules

Implement round grouping in `web/trace_viewer.js`; do not ask the backend for new data.

### Round Definition

- `run_started` is a pre-loop event and should not count as an Agentic Loop round.
- Every `context_built` event starts a new round.
- Events after a `context_built` belong to that round until the next `context_built`.
- `final_answer` and `run_completed` belong to the latest round.
- `run_failed` and `run_interrupted` belong to the latest round if one exists; otherwise show them in a system round.
- The top statistic "轮次" counts rounds that contain an `llm_decision`.

### Round Labels

Use stable labels:

```text
第 1 轮
第 2 轮
第 3 轮
```

Each round list item should also show a compact summary:

- selected action, such as `list_dir`, `read_file`, or `final_answer`
- status, from the latest event in that round
- number of events inside the round

### Step Order

Inside a selected round, render events in trace order. Use the original event `step` number as the stable order marker.

Expected V0.3/V0.4 example:

```text
第 1 轮
1. 整理上下文
2. 决定下一步
3. 调用工具：list_dir
4. 工具返回：list_dir
5. 吸收工具结果

第 2 轮
6. 整理上下文
7. 决定下一步
8. 调用工具：read_file
9. 工具返回：read_file
10. 吸收工具结果
```

---

## 4. Summary Metrics

Create `buildRunSummary(events)` in `web/trace_viewer.js`.

It must return this shape:

```js
{
  rounds: 0,
  modelCalls: 0,
  listDirCalls: 0,
  readFileCalls: 0,
  observations: 0
}
```

Definitions:

- `rounds`: number of grouped rounds containing `llm_decision`
- `modelCalls`: number of `llm_decision` events
- `listDirCalls`: number of `tool_started` events where `input.tool_name === "list_dir"`
- `readFileCalls`: number of `tool_started` events where `input.tool_name === "read_file"`
- `observations`: number of `observation_added` events

Render labels exactly:

```text
执行轮次
模型决策
list_dir 调用
read_file 调用
观察结果
```

Do not name the second metric "大模型调用", because FakeLLM mode does not call a real model. Use "模型决策" to cover both FakeLLM and DeepSeek.

---

## 5. Implementation Tasks

### Task 1: Add Source Tests For V0.4 Viewer Contracts

**Files:**

- Modify: `tests/test_trace_viewer_source.py`

- [ ] **Step 1: Add tests that fail before implementation**

Append these tests to `TraceViewerSourceTest`:

```python
    def test_viewer_contains_v4_layout_containers(self) -> None:
        html = (ROOT / "web" / "trace_viewer.html").read_text(encoding="utf-8")

        self.assertIn('id="run-summary"', html)
        self.assertIn('id="original-request"', html)
        self.assertIn('id="final-answer"', html)
        self.assertIn('id="round-list"', html)
        self.assertIn('id="round-detail"', html)
        self.assertLess(html.index('id="original-request"'), html.index('id="final-answer"'))
        self.assertLess(html.index('id="final-answer"'), html.index('id="round-list"'))

    def test_viewer_groups_events_by_agentic_loop_rounds(self) -> None:
        source = (ROOT / "web" / "trace_viewer.js").read_text(encoding="utf-8")

        self.assertIn("selectedRoundId", source)
        self.assertIn("function buildRounds", source)
        self.assertIn("function buildRunSummary", source)
        self.assertIn("function renderRunSummary", source)
        self.assertIn("function renderOriginalRequest", source)
        self.assertIn("function renderRoundList", source)
        self.assertIn("function renderRoundDetail", source)
        self.assertIn("function renderEventStep", source)
        self.assertIn("context_built", source)
        self.assertIn("llm_decision", source)

    def test_model_decision_details_remain_explainable(self) -> None:
        source = (ROOT / "web" / "trace_viewer.js").read_text(encoding="utf-8")

        self.assertIn("function renderModelDecisionStep", source)
        self.assertIn("System Prompt", source)
        self.assertIn("User Prompt", source)
        self.assertIn("message.content", source)
        self.assertIn("未调用大模型", source)
        self.assertIn("解析后的决策", source)
        self.assertIn("原始事件", source)

    def test_v0_4_does_not_add_agent_controls_or_external_assets(self) -> None:
        html = (ROOT / "web" / "trace_viewer.html").read_text(encoding="utf-8")
        source = (ROOT / "web" / "trace_viewer.js").read_text(encoding="utf-8")

        forbidden_html = [
            "https://",
            "http://",
            "cdn.",
            "bootstrap",
            "tailwind",
            "react",
            "vue",
            "onclick=\"pause",
            "onclick=\"resume",
            "onclick=\"retry",
        ]
        for token in forbidden_html:
            self.assertNotIn(token, html.lower())

        forbidden_source = [
            "fetch(\"/run",
            "fetch('/run",
            "pauseAgent",
            "resumeAgent",
            "retryAgent",
            "editGoal",
        ]
        for token in forbidden_source:
            self.assertNotIn(token, source)
```

- [ ] **Step 2: Run the focused source tests**

Run:

```bash
python3 -m unittest tests.test_trace_viewer_source
```

Expected before implementation:

```text
FAILED
```

The failure should be about missing V0.4 containers or function names. If it fails for unrelated syntax/import reasons, stop and report.

---

### Task 2: Update HTML Structure

**Files:**

- Modify: `web/trace_viewer.html`

- [ ] **Step 1: Replace the body layout with the V0.4 container order**

Keep the existing `<head>` and stylesheet link. Replace only the content inside `<main class="shell">` with:

```html
      <header class="status">
        <div>
          <p class="eyebrow">Min Agent Trace Viewer</p>
          <h1 id="current-title">等待任务开始</h1>
        </div>
        <span id="run-status" class="badge">waiting</span>
      </header>

      <section class="run-summary" aria-label="Run summary">
        <div id="run-summary" class="run-summary-grid"></div>
      </section>

      <section class="original-request">
        <h2>原始需求</h2>
        <p id="original-request">等待任务开始。</p>
      </section>

      <section class="result">
        <h2>最终结果</h2>
        <p id="final-answer">任务完成后展示最终回答。</p>
      </section>

      <section class="layout" aria-label="Agentic loop trace">
        <ol id="round-list" class="round-list">
          <li class="empty">等待 Trace 事件...</li>
        </ol>

        <aside class="detail">
          <h2>轮次详情</h2>
          <div id="round-detail" class="round-detail">暂无事件。</div>
        </aside>
      </section>
```

- [ ] **Step 2: Verify no duplicate old containers remain**

Run:

```bash
rg -n "timeline|step-detail|round-list|round-detail|original-request|run-summary" web/trace_viewer.html
```

Expected:

```text
web/trace_viewer.html:... id="run-summary"
web/trace_viewer.html:... id="original-request"
web/trace_viewer.html:... id="round-list"
web/trace_viewer.html:... id="round-detail"
```

There should be no `id="timeline"` and no `id="step-detail"`.

---

### Task 3: Add Summary And Round State

**Files:**

- Modify: `web/trace_viewer.js`

- [ ] **Step 1: Replace selected step state with selected round state**

Change:

```js
const state = {
  status: "waiting",
  events: [],
  selectedStep: null,
};
```

to:

```js
const state = {
  status: "waiting",
  events: [],
  selectedRoundId: null,
};
```

- [ ] **Step 2: Add summary helpers below `isTerminalStatus`**

Add:

```js
function buildRunSummary(events) {
  const rounds = buildRounds(events);
  return {
    rounds: rounds.filter((round) => round.events.some((event) => event.phase === "llm_decision")).length,
    modelCalls: events.filter((event) => event.phase === "llm_decision").length,
    listDirCalls: events.filter((event) => event.phase === "tool_started" && event.input?.tool_name === "list_dir").length,
    readFileCalls: events.filter((event) => event.phase === "tool_started" && event.input?.tool_name === "read_file").length,
    observations: events.filter((event) => event.phase === "observation_added").length,
  };
}

function renderRunSummary() {
  const summary = buildRunSummary(state.events);
  const container = document.querySelector("#run-summary");
  container.replaceChildren();

  const items = [
    ["执行轮次", summary.rounds],
    ["模型决策", summary.modelCalls],
    ["list_dir 调用", summary.listDirCalls],
    ["read_file 调用", summary.readFileCalls],
    ["观察结果", summary.observations],
  ];

  for (const [label, value] of items) {
    const item = document.createElement("div");
    item.className = "summary-item";

    const valueNode = document.createElement("strong");
    valueNode.textContent = String(value);

    const labelNode = document.createElement("span");
    labelNode.textContent = label;

    item.append(valueNode, labelNode);
    container.append(item);
  }
}
```

- [ ] **Step 3: Run focused tests**

Run:

```bash
python3 -m unittest tests.test_trace_viewer_source
```

Expected: still failing until all V0.4 functions and containers are wired.

---

### Task 4: Implement Round Grouping

**Files:**

- Modify: `web/trace_viewer.js`

- [ ] **Step 1: Add `buildRounds(events)` below `buildRunSummary`**

```js
function buildRounds(events) {
  const rounds = [];
  let currentRound = null;
  let loopIndex = 0;

  for (const event of events) {
    if (event.phase === "run_started") {
      continue;
    }

    if (event.phase === "context_built") {
      loopIndex += 1;
      currentRound = {
        id: `round-${loopIndex}`,
        index: loopIndex,
        title: `第 ${loopIndex} 轮`,
        events: [],
      };
      rounds.push(currentRound);
    }

    if (!currentRound) {
      currentRound = {
        id: "system",
        index: 0,
        title: "系统事件",
        events: [],
      };
      rounds.push(currentRound);
    }

    currentRound.events.push(event);
  }

  return rounds.map(enrichRound);
}
```

- [ ] **Step 2: Add `enrichRound(round)` below `buildRounds`**

```js
function enrichRound(round) {
  const latest = round.events[round.events.length - 1];
  const decision = round.events.find((event) => event.phase === "llm_decision");
  const toolStarted = round.events.find((event) => event.phase === "tool_started");
  const finalAnswer = round.events.find((event) => event.phase === "final_answer");
  const action = decision?.output?.kind === "final_answer"
    ? "final_answer"
    : toolStarted?.input?.tool_name || finalAnswer?.phase || decision?.output?.tool_name || "观察事件";

  return {
    ...round,
    latestStatus: latest?.status || "waiting",
    action,
    eventCount: round.events.length,
  };
}
```

- [ ] **Step 3: Add selected round helper**

```js
function selectedRound() {
  const rounds = buildRounds(state.events);
  return rounds.find((round) => round.id === state.selectedRoundId) || rounds[rounds.length - 1] || null;
}
```

Remove the old `selectedEvent()` helper after no call sites remain.

---

### Task 5: Render The Round List

**Files:**

- Modify: `web/trace_viewer.js`

- [ ] **Step 1: Update `applyEvent(event)`**

Replace the old selected step assignment:

```js
  state.selectedStep = event.step;
```

with:

```js
  const rounds = buildRounds(state.events);
  const latestRound = rounds[rounds.length - 1];
  state.selectedRoundId = latestRound?.id || null;
```

- [ ] **Step 2: Replace `renderTimeline()` with `renderRoundList()`**

```js
function renderRoundList() {
  const roundList = document.querySelector("#round-list");
  const rounds = buildRounds(state.events);
  roundList.replaceChildren();

  if (rounds.length === 0) {
    const empty = document.createElement("li");
    empty.className = "empty";
    empty.textContent = "等待 Trace 事件...";
    roundList.append(empty);
    return;
  }

  for (const round of rounds) {
    const item = document.createElement("li");
    if (round.id === state.selectedRoundId) {
      item.className = "active";
    }

    const button = document.createElement("button");
    button.type = "button";

    const content = document.createElement("span");
    content.className = "round-content";

    const title = document.createElement("span");
    title.textContent = round.title;

    const meta = document.createElement("small");
    meta.textContent = `${round.action} · ${round.latestStatus} · ${round.eventCount} 步`;

    content.append(title, meta);

    const badge = document.createElement("span");
    badge.className = "agent-module-badge";
    badge.textContent = "Agentic Loop";

    button.append(content, badge);
    button.addEventListener("click", () => {
      state.selectedRoundId = round.id;
      render();
    });

    item.append(button);
    roundList.append(item);
  }
}
```

- [ ] **Step 3: Keep `moduleForPhase` only if used in details**

If `moduleForPhase` is still used by event-step detail badges, keep it. If it has no call sites, remove it and update old source tests that expected flat timeline badges.

---

### Task 6: Render Selected Round Details And Ordered Steps

**Files:**

- Modify: `web/trace_viewer.js`

- [ ] **Step 1: Replace `renderDetail()` with `renderRoundDetail()`**

```js
function renderRoundDetail() {
  const round = selectedRound();
  const detail = document.querySelector("#round-detail");
  detail.replaceChildren();

  if (!round) {
    detail.textContent = "暂无事件。";
    return;
  }

  const heading = document.createElement("div");
  heading.className = "detail-heading";

  const title = document.createElement("h3");
  title.textContent = round.title;

  const meta = document.createElement("p");
  meta.className = "detail-meta";
  meta.textContent = `${round.action} · ${round.latestStatus} · ${round.eventCount} 步`;

  heading.append(title, meta);
  detail.append(heading);

  const steps = document.createElement("div");
  steps.className = "round-steps";
  for (const event of round.events) {
    renderEventStep(steps, event);
  }
  detail.append(steps);
}
```

- [ ] **Step 2: Add `renderEventStep(container, event)`**

```js
function renderEventStep(container, event) {
  const step = document.createElement("section");
  step.className = "event-step";

  const header = document.createElement("div");
  header.className = "event-step-header";

  const number = document.createElement("span");
  number.className = "event-step-number";
  number.textContent = String(event.step);

  const heading = document.createElement("div");
  const title = document.createElement("h3");
  title.textContent = event.title;

  const meta = document.createElement("p");
  meta.className = "detail-meta";
  meta.textContent = `${moduleForPhase(event.phase)} · ${event.phase} · ${event.status}`;

  heading.append(title, meta);
  header.append(number, heading);
  step.append(header);

  if (event.reason) {
    appendSection(step, "为什么发生", event.reason);
  }

  if (event.phase === "llm_decision") {
    renderModelDecisionStep(step, event);
  } else {
    appendSection(step, "输入", event.input);
    appendSection(step, "输出", event.output);
  }

  appendSection(step, "原始事件", event);
  container.append(step);
}
```

- [ ] **Step 3: Preserve readable empty input/output**

Update `formatValue(value)` so empty objects do not render as unclear blank content:

```js
function formatValue(value) {
  if (typeof value === "string") {
    return value || "无内容";
  }
  if (value === null || value === undefined) {
    return "无内容";
  }
  if (typeof value === "object" && Object.keys(value).length === 0) {
    return "无内容";
  }
  return JSON.stringify(value, null, 2);
}
```

---

### Task 7: Render Model Decision Details

**Files:**

- Modify: `web/trace_viewer.js`

- [ ] **Step 1: Replace `renderModelCall` call sites with `renderModelDecisionStep`**

Add:

```js
function renderModelDecisionStep(container, event) {
  const modelCall = event.output?.metadata?.model_call;
  const section = appendSectionShell(container, "模型决策");

  if (!modelCall) {
    const empty = document.createElement("p");
    empty.className = "model-call-empty";
    empty.textContent = "未调用大模型：当前使用 FakeLLM 本地决策器。";
    section.append(empty);
  } else {
    const badge = document.createElement("p");
    badge.className = "model-call-badge";
    badge.textContent = `已调用大模型：${modelCall.provider || "unknown"} / ${modelCall.model || "unknown"}`;
    section.append(badge);

    const request = modelCall.request || {};
    appendCodeBlock(section, "System Prompt", request.system_prompt || "");
    appendCodeBlock(section, "User Prompt", request.user_prompt || "");

    const response = modelCall.response || {};
    appendCodeBlock(section, "大模型返回 message.content", response.content || response.error || "");
  }

  renderDecision(section, event.output);
}
```

- [ ] **Step 2: Keep parsed decision compact**

Keep or update `renderDecision(container, output)` to include only these fields:

```js
function renderDecision(container, output) {
  const decision = {
    kind: output?.kind,
    tool_name: output?.tool_name,
    args: output?.args,
    reason: output?.reason,
    message: output?.message,
    success: output?.success,
  };
  appendSection(container, "解析后的决策", compactObject(decision));
}
```

This prevents the `metadata.model_call` payload from appearing twice.

---

### Task 8: Wire The Render Flow

**Files:**

- Modify: `web/trace_viewer.js`

- [ ] **Step 1: Add original request renderer**

```js
function renderOriginalRequest() {
  const runStarted = state.events.find((event) => event.phase === "run_started");
  const goal = runStarted?.input?.user_goal;
  document.querySelector("#original-request").textContent = goal || "等待任务开始。";
}
```

- [ ] **Step 2: Update `render()`**

Replace:

```js
function render() {
  renderStatus();
  renderTimeline();
  renderDetail();
  renderFinalAnswer();
}
```

with:

```js
function render() {
  renderStatus();
  renderRunSummary();
  renderOriginalRequest();
  renderFinalAnswer();
  renderRoundList();
  renderRoundDetail();
}
```

- [ ] **Step 3: Update `setStatus(status)`**

Keep it simple:

```js
function setStatus(status) {
  state.status = status;
  renderStatus();
}
```

No need to render the whole page on transient SSE reconnect errors.

- [ ] **Step 4: Remove obsolete functions**

Remove these only after their call sites are gone:

```text
selectedEvent
renderTimeline
renderDetail
renderModelCall
```

Do not remove:

```text
renderDecision
appendSection
appendSectionShell
appendCodeBlock
appendPre
formatValue
compactObject
moduleForPhase
```

unless the final code has no call sites.

---

### Task 9: Update CSS Without A Visual Redesign

**Files:**

- Modify: `web/trace_viewer.css`

- [ ] **Step 1: Add new containers to the existing card style**

Change:

```css
.status,
.layout,
.result {
```

to:

```css
.status,
.run-summary,
.original-request,
.layout,
.result {
```

- [ ] **Step 2: Add spacing and summary grid**

```css
.run-summary,
.original-request,
.result {
  margin-top: 20px;
  padding: 24px;
}

.run-summary-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.summary-item {
  display: grid;
  gap: 4px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #f9fafb;
  padding: 12px;
}

.summary-item strong {
  color: #111827;
  font-size: 24px;
  line-height: 1;
}

.summary-item span {
  color: #667085;
  font-size: 13px;
}
```

- [ ] **Step 3: Rename timeline styles for rounds**

Replace `.timeline` selectors with `.round-list` selectors and `.timeline-content` with `.round-content`.

Use this shape:

```css
.round-list {
  margin: 0;
  padding: 24px 24px 24px 44px;
}

.round-list li {
  margin-bottom: 16px;
}

.round-list button {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  border: 1px solid #d8dee8;
  border-radius: 6px;
  background: #ffffff;
  padding: 12px;
  text-align: left;
  cursor: pointer;
}

.round-content {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.round-list .active button {
  border-color: #2563eb;
  background: #eff6ff;
}

.round-list small {
  color: #667085;
}

.round-list .active .agent-module-badge {
  border-color: #93c5fd;
  background: #dbeafe;
  color: #1d4ed8;
}
```

- [ ] **Step 4: Add detail step styles**

```css
.round-detail,
.round-steps {
  display: grid;
  gap: 14px;
}

.event-step {
  display: grid;
  gap: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 14px;
}

.event-step-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.event-step-number {
  display: inline-grid;
  place-items: center;
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 700;
  font-size: 13px;
}
```

- [ ] **Step 5: Update mobile layout**

Inside the existing `@media (max-width: 800px)` block, add:

```css
  .run-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .round-list button {
    align-items: flex-start;
    flex-direction: column;
  }
```

Remove or replace the old `.timeline button` mobile rule.

---

### Task 10: Update Docs For V0.4 Boundary

**Files:**

- Modify: `AGENTS.md`
- Modify: `CHANGELOG.md`
- Modify: `README.md`
- Modify: `docs/runbook.md`

- [ ] **Step 1: Update `AGENTS.md`**

Add a V0.4 section after the V0.3 section:

```markdown
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
```

- [ ] **Step 2: Update `CHANGELOG.md`**

Add a V0.4 entry above V0.3:

```markdown
## V0.4: Trace Viewer 可理解性增强

V0.4 让观察窗口从“按事件平铺”升级为“按 Agentic Loop 轮次理解”。

使用者现在可以先看到本次任务的统计、原始需求和最终结果，再进入观察窗口查看每一轮中 Agent 如何整理上下文、做出决策、调用工具、吸收观察结果。大模型决策步骤会展示发送给模型的内容、模型返回内容，以及解析后的本地 `AgentAction`。

这一版只改进 Trace Viewer 的展示方式，不改变 Agent 执行逻辑，不新增工具，不写 workspace 文件，也不让页面控制 Agent。

完成标准：

- 顶部展示执行轮次、模型决策、工具调用和观察结果统计。
- 原始需求展示在最终结果上方。
- 最终结果展示在观察窗口上方。
- 观察窗口左侧按轮次展示，右侧按步骤展示该轮详情。
- FakeLLM 和 DeepSeek 的决策详情都可解释。
```

- [ ] **Step 3: Update `README.md`**

Add after V0.3:

```markdown
## V0.4: 轮次化 Trace Viewer

V0.4 改进了浏览器观察窗口的可理解性。页面顶部会展示本次任务的执行统计、用户输入的原始需求和最终结果；下方观察窗口按 Agentic Loop 轮次组织执行过程，每一轮内部继续保留具体步骤、输入、输出和原始事件 JSON。

DeepSeek 模式下，模型决策步骤会展示发送给模型的 System Prompt、User Prompt、模型返回的 `message.content`，以及解析后的本地 `AgentAction`。FakeLLM 模式下，页面会明确说明没有调用真实大模型。
```

- [ ] **Step 4: Update `docs/runbook.md`**

Add a V0.4 verification section:

```markdown
## V0.4 Trace Viewer 验证

1. 运行测试：

   ```bash
   python3 -m unittest discover -s tests
   ```

2. 运行 fake 模式 demo：

   ```bash
   PYTHONPATH=src python3 -m min_agent.cli \
     "请总结这个 demo 的使用方式" \
     --workspace examples/workspace \
     --port 8765
   ```

3. 在浏览器中确认：

   - 顶部统计能看到执行轮次、模型决策、`list_dir` 调用、`read_file` 调用和观察结果。
   - 原始需求在最终结果上方。
   - 最终结果在观察窗口上方。
   - 左侧是 Agentic Loop 轮次，不是二十多个平铺事件。
   - 点击任意轮次，右侧展示该轮内部的有序步骤。
   - 每个步骤能看到输入、输出和原始事件 JSON。
   - 模型决策步骤能看到 FakeLLM 说明或 DeepSeek 请求/响应详情。
```

---

## 6. Required Verification

Run all commands from repository root:

```bash
python3 -m unittest tests.test_trace_viewer_source
```

Expected:

```text
OK
```

Then run:

```bash
python3 -m unittest discover -s tests
```

Expected:

```text
OK
```

Run non-browser smoke:

```bash
PYTHONPATH=src python3 -m min_agent.cli \
  "请总结这个 demo 的使用方式" \
  --workspace examples/workspace \
  --no-viewer \
  --no-browser \
  --step-delay 0
```

Expected:

- exit code `0`
- CLI prints a final answer
- CLI prints a run record path under `runs/`
- no API key is required in default fake mode

Run browser smoke:

```bash
PYTHONPATH=src python3 -m min_agent.cli \
  "请总结这个 demo 的使用方式" \
  --workspace examples/workspace \
  --port 8765
```

Manual browser checks:

- The page is not blank.
- Header status updates as the run progresses.
- Statistics are visible above the original request.
- Original request appears above final result.
- Final result appears above the observation window.
- Left side shows rounds, not a flat list of 20+ events.
- Right side shows ordered steps for the selected round.
- `llm_decision` step shows model decision details.
- Input/output sections do not overlap and remain readable on desktop width.
- Browser console has no JavaScript errors.

Final repository checks:

```bash
git diff --check
git status --short
```

Expected:

- `git diff --check` reports no whitespace errors.
- `git status --short` only includes intentional V0.4 files.

---

## 7. Stop Conditions

Stop and report instead of continuing if any of these happen:

- A V0.4 requirement appears to require modifying a forbidden Python runtime file.
- Existing tests fail for reasons unrelated to viewer source assertions.
- The page becomes blank.
- Browser console shows a JavaScript exception.
- A proposed fix requires a new dependency.
- A proposed fix changes the Agent execution loop, trace schema, tool behavior, or DeepSeek contract.
- A proposed fix adds page controls that can change Agent execution.
- The implementation cannot show model request/response details from the existing `metadata.model_call`.
- The implementation needs to write `.env`, read secrets, or modify API key handling.

When stopping, report:

```text
Blocked at: <task and step>
Reason: <specific problem>
Evidence: <test output, console error, or file/line>
Suggested next decision: <one concrete option>
```

---

## 8. Completion Report Format

After implementation and verification, report in this exact structure:

```markdown
## V0.4 Completion Report

### Changed Files

- `web/trace_viewer.html`: <one sentence>
- `web/trace_viewer.css`: <one sentence>
- `web/trace_viewer.js`: <one sentence>
- `tests/test_trace_viewer_source.py`: <one sentence>
- `AGENTS.md`: <one sentence>
- `CHANGELOG.md`: <one sentence>
- `README.md`: <one sentence>
- `docs/runbook.md`: <one sentence>

### Verification

- `python3 -m unittest tests.test_trace_viewer_source`: <PASS/FAIL>
- `python3 -m unittest discover -s tests`: <PASS/FAIL>
- fake non-browser smoke: <PASS/FAIL>
- browser manual smoke: <PASS/FAIL and short note>
- `git diff --check`: <PASS/FAIL>

### Product Acceptance

- Top statistics: <yes/no>
- Original request above final result: <yes/no>
- Final result above observation window: <yes/no>
- Left side round grouping: <yes/no>
- Right side ordered round steps: <yes/no>
- Explainable input/output per step: <yes/no>
- FakeLLM decision explanation: <yes/no>
- DeepSeek model-call detail support: <yes/no or not manually tested>

### Notes

- <Only include actual caveats. Do not invent risks.>
```

Do not commit or push unless the user explicitly asks for it.
