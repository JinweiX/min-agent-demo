const state = {
  status: "waiting",
  events: [],
  selectedEvent: null,
};

function applyEvent(event) {
  state.events.push(event);
  state.selectedEvent = event;
  if (event.status) {
    state.status = event.status;
  }
  render();
}

function render() {
  renderStatus();
  renderTimeline();
  renderDetail();
  renderFinalAnswer();
}

function renderStatus() {
  const status = document.querySelector("#run-status");
  const heading = document.querySelector("h1");
  status.textContent = state.status;
  heading.textContent = state.selectedEvent?.title || "等待任务开始";
}

function renderTimeline() {
  const timeline = document.querySelector("#timeline");
  timeline.replaceChildren();

  if (state.events.length === 0) {
    const empty = document.createElement("li");
    empty.className = "empty";
    empty.textContent = "Trace events will appear here.";
    timeline.append(empty);
    return;
  }

  for (const event of state.events) {
    const item = document.createElement("li");
    item.textContent = `${event.step ?? "-"} · ${event.title ?? event.phase ?? "event"}`;
    item.addEventListener("click", () => {
      state.selectedEvent = event;
      renderDetail();
    });
    timeline.append(item);
  }
}

function renderDetail() {
  const detail = document.querySelector("#step-detail");
  detail.textContent = state.selectedEvent
    ? JSON.stringify(state.selectedEvent, null, 2)
    : "No event selected.";
}

function renderFinalAnswer() {
  const finalAnswer = document.querySelector("#final-answer");
  const finalEvent = state.events.find((event) => event.phase === "final_answer");
  finalAnswer.textContent = finalEvent?.output?.message || "任务完成后展示最终回答。";
}

function connectTraceStream() {
  if (!("EventSource" in window)) {
    console.warn("EventSource is not available in this browser.");
    return;
  }

  const stream = new EventSource("/events");
  stream.onmessage = (message) => {
    applyEvent(JSON.parse(message.data));
  };
  stream.onerror = () => {
    state.status = "reconnecting";
    renderStatus();
  };
}

render();
connectTraceStream();

