const state = {
  status: "waiting",
  events: [],
  selectedStep: null,
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
  state.selectedStep = event.step;
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

function selectedEvent() {
  return state.events.find((event) => event.step === state.selectedStep) || null;
}

function moduleForPhase(phase) {
  const modules = {
    "run_started": "Goal",
    "context_built": "Context",
    "llm_decision": "Model / Reasoning",
    "tool_started": "Tools",
    "tool_finished": "Tools",
    "observation_added": "Memory / State",
    "final_answer": "Agent Loop",
    "run_completed": "Agent Loop",
    "run_failed": "Agent Loop",
    "run_interrupted": "Agent Loop",
  };
  return modules[phase] || "Agent Loop";
}

function render() {
  renderStatus();
  renderTimeline();
  renderDetail();
  renderFinalAnswer();
}

function renderStatus() {
  document.querySelector("#run-status").textContent = state.status;
  const latest = state.events[state.events.length - 1];
  document.querySelector("#current-title").textContent = latest?.title || "等待任务开始";
}

function renderTimeline() {
  const timeline = document.querySelector("#timeline");
  timeline.replaceChildren();

  if (state.events.length === 0) {
    const empty = document.createElement("li");
    empty.className = "empty";
    empty.textContent = "等待 Trace 事件...";
    timeline.append(empty);
    return;
  }

  for (const event of state.events) {
    const item = document.createElement("li");
    if (event.step === state.selectedStep) {
      item.className = "active";
    }

    const button = document.createElement("button");
    button.type = "button";

    const content = document.createElement("span");
    content.className = "timeline-content";

    const title = document.createElement("span");
    title.textContent = `${event.step}. ${event.title}`;

    const meta = document.createElement("small");
    meta.textContent = `${event.phase} · ${event.status}`;

    const module = document.createElement("span");
    module.className = "agent-module-badge";
    module.textContent = moduleForPhase(event.phase);

    content.append(title, meta);
    button.append(content, module);
    button.addEventListener("click", () => {
      state.selectedStep = event.step;
      render();
    });

    item.append(button);
    timeline.append(item);
  }
}

function renderDetail() {
  const event = selectedEvent();
  const detail = document.querySelector("#step-detail");
  detail.replaceChildren();

  if (!event) {
    detail.textContent = "暂无事件。";
    return;
  }

  const heading = document.createElement("div");
  heading.className = "detail-heading";

  const title = document.createElement("h3");
  title.textContent = `${event.step}. ${event.title}`;

  const meta = document.createElement("p");
  meta.className = "detail-meta";
  meta.textContent = `${event.phase} · ${event.status}`;

  heading.append(title, meta);
  detail.append(heading);

  if (event.phase === "llm_decision") {
    renderModelCall(detail, event);
    renderDecision(detail, event.output);
  } else {
    appendSection(detail, "事件输出", event.output);
  }

  appendSection(detail, "原始事件", event);
}

function renderModelCall(container, event) {
  const modelCall = event.output?.metadata?.model_call;
  const section = appendSectionShell(container, "模型调用");

  if (!modelCall) {
    const empty = document.createElement("p");
    empty.className = "model-call-empty";
    empty.textContent = "未调用大模型：当前使用 FakeLLM 本地决策器。";
    section.append(empty);
    return;
  }

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

function appendSection(container, title, value) {
  const section = appendSectionShell(container, title);
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
    return value;
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
