const state = {
  status: "waiting",
  events: [],
  selectedRoundId: null,
};

function connectTraceStream() {
  if (!("EventSource" in window)) {
    setStatus("unsupported");
    return;
  }

  const stream = new EventSource("/events");
  stream.onmessage = (message) => {
    const event = JSON.parse(message.data);
    applyEvent(event);
  };
  stream.onerror = () => {
    if (!isTerminalStatus(state.status)) {
      setStatus("reconnecting");
    }
  };
}

function applyEvent(event) {
  const existingIndex = state.events.findIndex((item) => item.step === event.step);
  if (existingIndex >= 0) {
    state.events[existingIndex] = event;
  } else {
    state.events.push(event);
  }
  const rounds = buildRounds(state.events);
  const latestRound = rounds[rounds.length - 1];
  if (["run_completed", "run_failed", "run_interrupted"].includes(event.phase)) {
    state.selectedRoundId = "task-completion";
  } else {
    state.selectedRoundId = latestRound?.id || (event.phase === "run_started" ? "task-entry" : null);
  }
  state.status = event.status || state.status;
  render();
}

function setStatus(status) {
  state.status = status;
  renderStatus();
}

function isTerminalStatus(status) {
  return ["completed", "failed", "interrupted"].includes(status);
}

function buildRunSummary(events) {
  const rounds = buildRounds(events);
  return {
    rounds: rounds.filter((round) => round.events.some((event) => event.phase === "llm_decision")).length,
    modelCalls: events.filter((event) => event.phase === "llm_decision").length,
    toolCalls: events.filter((event) => event.phase === "tool_started").length,
    permissions: events.filter((event) => event.phase === "permission_requested").length,
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
    ["工具调用", summary.toolCalls],
    ["权限请求", summary.permissions],
    ["观察结果", summary.observations],
  ];

  for (const [label, value] of items) {
    const item = document.createElement("div");
    item.className = "summary-item";

    const valueNode = document.createElement("strong");
    valueNode.className = "summary-value";
    valueNode.textContent = String(value);

    const labelNode = document.createElement("span");
    labelNode.className = "summary-label";
    labelNode.textContent = label;

    item.append(valueNode, labelNode);
    container.append(item);
  }
}

function buildRounds(events) {
  const rounds = [];
  let currentRound = null;
  let loopIndex = 0;

  for (const event of events) {
    if (["run_started", "run_completed", "run_failed", "run_interrupted"].includes(event.phase)) {
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

function selectedRound() {
  const rounds = buildRounds(state.events);
  return rounds.find((round) => round.id === state.selectedRoundId) || rounds[rounds.length - 1] || null;
}

function runStartedEvent() {
  return state.events.find((event) => event.phase === "run_started") || null;
}

function terminalEvent() {
  return state.events.find((event) => ["run_completed", "run_failed", "run_interrupted"].includes(event.phase)) || null;
}

function moduleForPhase(phase) {
  const modules = {
    "run_started": "Goal",
    "context_built": "Context",
    "llm_decision": "Model / Reasoning",
    "tool_started": "Tools",
    "tool_finished": "Tools",
    "observation_added": "Memory / State",
    "permission_requested": "Permission",
    "permission_resolved": "Permission",
    "final_answer": "Agent Loop",
    "run_completed": "Agent Loop",
    "run_failed": "Agent Loop",
    "run_interrupted": "Agent Loop",
  };
  return modules[phase] || "Agent Loop";
}

function renderOriginalRequest() {
  const runStarted = state.events.find((event) => event.phase === "run_started");
  const goal = runStarted?.input?.user_goal;
  document.querySelector("#original-request").textContent = goal || "等待任务开始。";
}

function render() {
  renderStatus();
  renderRunSummary();
  renderOriginalRequest();
  renderFinalAnswer();
  renderRoundList();
  renderRoundDetail();
}

function renderStatus() {
  document.querySelector("#run-status").textContent = state.status;
  const latest = state.events[state.events.length - 1];
  document.querySelector("#current-title").textContent = latest?.title || "等待任务开始";
}

function renderRoundList() {
  const roundList = document.querySelector("#round-list");
  const rounds = buildRounds(state.events);
  const entry = runStartedEvent();
  const completion = terminalEvent();
  roundList.replaceChildren();

  if (!entry && rounds.length === 0 && !completion) {
    const empty = document.createElement("li");
    empty.className = "empty";
    empty.textContent = "等待 Trace 事件...";
    roundList.append(empty);
    return;
  }

  if (entry) {
    renderTaskEntryItem(roundList, entry);
  }

  for (const round of rounds) {
    const item = document.createElement("li");
    if (round.id === state.selectedRoundId) {
      item.className = "active";
    }

    const button = document.createElement("button");
    button.type = "button";

    const roundIndex = document.createElement("span");
    roundIndex.className = "round-index";
    roundIndex.textContent = String(round.index || "");

    const content = document.createElement("span");
    content.className = "round-content";

    const header = document.createElement("span");
    header.className = "round-header";

    const title = document.createElement("span");
    title.className = "round-title";
    title.textContent = round.title;

    const statusDot = document.createElement("span");
    statusDot.className = `round-status-dot status-${round.latestStatus}`;
    statusDot.setAttribute("aria-hidden", "true");

    header.append(title, statusDot);

    const meta = document.createElement("small");
    meta.textContent = `${round.action} · ${round.latestStatus}`;

    const stepCount = document.createElement("span");
    stepCount.className = "round-step-count";
    stepCount.textContent = `${round.eventCount} 步`;

    content.append(header, meta);

    const badge = document.createElement("span");
    badge.className = "agent-module-badge";
    badge.textContent = "Agentic Loop";

    button.append(roundIndex, content, stepCount, badge);
    button.addEventListener("click", () => {
      state.selectedRoundId = round.id;
      render();
    });

    item.append(button);
    roundList.append(item);
  }

  if (completion) {
    const completionDisplayIndex = rounds.length + 1;
    renderTaskCompletionItem(roundList, completion, completionDisplayIndex);
  }
}

function renderTaskEntryItem(roundList, event) {
  const item = document.createElement("li");
  item.className = "task-entry";
  if (state.selectedRoundId === "task-entry") {
    item.classList.add("active");
  }

  const button = document.createElement("button");
  button.type = "button";

  const roundIndex = document.createElement("span");
  roundIndex.className = "round-index";
  roundIndex.textContent = "起";

  const content = document.createElement("span");
  content.className = "round-content";

  const header = document.createElement("span");
  header.className = "round-header";

  const title = document.createElement("span");
  title.className = "round-title";
  title.textContent = "任务入口";

  const statusDot = document.createElement("span");
  statusDot.className = `round-status-dot status-${event.status}`;
  statusDot.setAttribute("aria-hidden", "true");

  header.append(title, statusDot);

  const meta = document.createElement("small");
  meta.textContent = `CLI · ${event.phase} · ${event.status}`;

  const stepCount = document.createElement("span");
  stepCount.className = "round-step-count";
  stepCount.textContent = "1 步";

  content.append(header, meta);

  const badge = document.createElement("span");
  badge.className = "agent-module-badge";
  badge.textContent = "Run Start";

  button.append(roundIndex, content, stepCount, badge);
  button.addEventListener("click", () => {
    state.selectedRoundId = "task-entry";
    render();
  });

  item.append(button);
  roundList.append(item);
}

function renderTaskCompletionItem(roundList, event, displayIndex) {
  const item = document.createElement("li");
  item.className = "task-completion";
  if (state.selectedRoundId === "task-completion") {
    item.classList.add("active");
  }

  const button = document.createElement("button");
  button.type = "button";

  const roundIndex = document.createElement("span");
  roundIndex.className = "round-index";
  roundIndex.textContent = String(displayIndex);

  const content = document.createElement("span");
  content.className = "round-content";

  const header = document.createElement("span");
  header.className = "round-header";

  const title = document.createElement("span");
  title.className = "round-title";
  title.textContent = event.phase === "run_completed" ? "任务完成" : "任务结束";

  const statusDot = document.createElement("span");
  statusDot.className = `round-status-dot status-${event.status}`;
  statusDot.setAttribute("aria-hidden", "true");

  header.append(title, statusDot);

  const meta = document.createElement("small");
  meta.textContent = `CLI · ${event.phase} · ${event.status}`;

  const stepCount = document.createElement("span");
  stepCount.className = "round-step-count";
  stepCount.textContent = "1 步";

  content.append(header, meta);

  const badge = document.createElement("span");
  badge.className = "agent-module-badge";
  badge.textContent = "Run Completed";

  button.append(roundIndex, content, stepCount, badge);
  button.addEventListener("click", () => {
    state.selectedRoundId = "task-completion";
    render();
  });

  item.append(button);
  roundList.append(item);
}

function renderRoundDetail() {
  const round = selectedRound();
  const detail = document.querySelector("#round-detail");
  detail.replaceChildren();

  if (state.selectedRoundId === "task-entry") {
    renderTaskEntryDetail(detail);
    return;
  }

  if (state.selectedRoundId === "task-completion") {
    renderTaskCompletionDetail(detail);
    return;
  }

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
  renderFlowOverview(detail, round.events);

  const steps = document.createElement("div");
  steps.className = "round-steps";
  for (const event of round.events) {
    renderEventStep(steps, event);
  }
  detail.append(steps);
}

function renderTaskEntryDetail(detail) {
  const event = runStartedEvent();
  if (!event) {
    detail.textContent = "暂无任务入口事件。";
    return;
  }

  const heading = document.createElement("div");
  heading.className = "detail-heading";

  const title = document.createElement("h3");
  title.textContent = "任务入口";

  const meta = document.createElement("p");
  meta.className = "detail-meta";
  meta.textContent = `CLI · ${event.phase} · ${event.status} · 1 步`;

  heading.append(title, meta);
  detail.append(heading);
  renderFlowOverview(detail, [event]);

  const steps = document.createElement("div");
  steps.className = "round-steps";
  renderEventStep(steps, event);
  detail.append(steps);
}

function renderTaskCompletionDetail(detail) {
  const event = terminalEvent();
  if (!event) {
    detail.textContent = "暂无任务完成事件。";
    return;
  }

  const heading = document.createElement("div");
  heading.className = "detail-heading";

  const title = document.createElement("h3");
  title.textContent = event.phase === "run_completed" ? "任务完成" : "任务结束";

  const meta = document.createElement("p");
  meta.className = "detail-meta";
  meta.textContent = `CLI · ${event.phase} · ${event.status} · 1 步`;

  heading.append(title, meta);
  detail.append(heading);
  renderFlowOverview(detail, [event]);

  const steps = document.createElement("div");
  steps.className = "round-steps";
  renderEventStep(steps, event);
  detail.append(steps);
}

function renderFlowOverview(container, events) {
  const flow = document.createElement("section");
  flow.className = "flow-overview";

  const title = document.createElement("h3");
  title.textContent = "本轮流程";

  const nodes = document.createElement("div");
  nodes.className = "flow-nodes";

  for (const item of buildFlowItems(events)) {
    const node = document.createElement("span");
    node.className = "flow-node";
    node.textContent = item;
    nodes.append(node);
  }

  flow.append(title, nodes);
  container.append(flow);
}

function buildFlowItems(events) {
  if (events.some((event) => event.phase === "run_started")) {
    return ["Goal", "CLI", "Run Started"];
  }
  if (events.some((event) => event.phase === "run_completed")) {
    return ["Final Answer", "Run Completed"];
  }
  if (events.some((event) => event.phase === "run_failed")) {
    return ["Final Answer", "Run Failed"];
  }
  if (events.some((event) => event.phase === "run_interrupted")) {
    return ["Final Answer", "Run Interrupted"];
  }

  const items = [];
  const add = (label) => {
    if (!items.includes(label)) {
      items.push(label);
    }
  };

  for (const event of events) {
    if (event.phase === "context_built") {
      add("Context");
    } else if (event.phase === "llm_decision") {
      add("Model");
    } else if (event.phase === "tool_started") {
      add(`Tool: ${event.input?.tool_name || "unknown"}`);
    } else if (event.phase === "permission_requested") {
      add("Permission Request");
    } else if (event.phase === "permission_resolved") {
      add(event.output?.approved ? "User Approved" : "User Rejected");
    } else if (event.phase === "observation_added") {
      add("Observation");
    } else if (event.phase === "final_answer") {
      add("Final Answer");
    } else if (event.phase === "run_completed") {
      add("Complete");
    } else if (event.phase === "run_failed") {
      add("Failed");
    } else if (event.phase === "run_interrupted") {
      add("Interrupted");
    }
  }

  return items.length > 0 ? items : ["Trace Event"];
}

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
    const ioGrid = document.createElement("div");
    ioGrid.className = "step-io-grid";
    appendSection(ioGrid, "输入", event.input);
    appendSection(ioGrid, "输出", event.output);
    step.append(ioGrid);
  }

  appendSection(step, "原始事件 JSON", event, "raw-event");
  container.append(step);
}

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

function appendSection(container, title, value, extraClassName = "") {
  const section = appendSectionShell(container, title);
  if (extraClassName) {
    section.classList.add(extraClassName);
  }
  appendPre(section, formatValue(value));
  return section;
}

function appendSectionShell(container, title) {
  const section = document.createElement("section");
  section.className = "detail-section";

  const heading = document.createElement("h3");
  heading.textContent = title;

  section.append(heading);
  container.append(section);
  return section;
}

function appendCodeBlock(container, title, value) {
  const label = document.createElement("h4");
  label.textContent = title;
  container.append(label);
  appendPre(container, value || "无内容");
}

function appendPre(container, text) {
  const pre = document.createElement("pre");
  pre.textContent = text;
  container.append(pre);
}

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

function compactObject(value) {
  return Object.fromEntries(Object.entries(value).filter((entry) => entry[1] !== undefined && entry[1] !== null));
}

function renderFinalAnswer() {
  const finalEvent = state.events.find((event) => event.phase === "final_answer");
  document.querySelector("#final-answer").textContent =
    finalEvent?.output?.message || "任务完成后展示最终回答。";
}

render();
connectTraceStream();
