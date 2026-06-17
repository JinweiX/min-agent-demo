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

    const title = document.createElement("span");
    title.textContent = `${event.step}. ${event.title}`;

    const meta = document.createElement("small");
    meta.textContent = `${event.phase} · ${event.status}`;

    button.append(title, meta);
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
  detail.textContent = event ? JSON.stringify(event, null, 2) : "暂无事件。";
}

function renderFinalAnswer() {
  const finalEvent = state.events.find((event) => event.phase === "final_answer");
  document.querySelector("#final-answer").textContent =
    finalEvent?.output?.message || "任务完成后展示最终回答。";
}

render();
connectTraceStream();
