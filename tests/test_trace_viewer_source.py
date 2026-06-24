from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TraceViewerSourceTest(unittest.TestCase):
    def test_eventsource_error_does_not_override_terminal_status(self) -> None:
        source = (ROOT / "web" / "trace_viewer.js").read_text(encoding="utf-8")

        self.assertIn("function isTerminalStatus", source)
        self.assertIn("if (!isTerminalStatus(state.status))", source)

    def test_step_detail_renders_model_call_sections(self) -> None:
        source = (ROOT / "web" / "trace_viewer.js").read_text(encoding="utf-8")

        self.assertIn("function renderModelDecisionStep", source)
        self.assertIn("大模型返回 message.content", source)
        self.assertIn("未调用大模型", source)
        self.assertIn("原始事件", source)

    def test_timeline_renders_agent_module_badges(self) -> None:
        source = (ROOT / "web" / "trace_viewer.js").read_text(encoding="utf-8")

        self.assertIn("function moduleForPhase", source)
        self.assertIn("agent-module-badge", source)
        self.assertIn('"context_built": "Context"', source)
        self.assertIn('"llm_decision": "Model / Reasoning"', source)
        self.assertIn('"tool_started": "Tools"', source)
        self.assertIn('"observation_added": "Memory / State"', source)
        self.assertIn('"final_answer": "Agent Loop"', source)

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

    def test_v0_4_viewer_uses_prototype_hierarchy_classes(self) -> None:
        html = (ROOT / "web" / "trace_viewer.html").read_text(encoding="utf-8")
        css = (ROOT / "web" / "trace_viewer.css").read_text(encoding="utf-8")
        source = (ROOT / "web" / "trace_viewer.js").read_text(encoding="utf-8")

        self.assertIn('class="summary-panel"', html)
        self.assertIn('class="context-panel original-request"', html)
        self.assertIn('class="context-panel result"', html)
        self.assertIn("round-index", source)
        self.assertIn("round-status-dot", source)
        self.assertIn("round-step-count", source)
        self.assertIn("step-io-grid", source)
        self.assertIn("raw-event", source)
        self.assertIn(".summary-value", css)
        self.assertIn(".round-index", css)
        self.assertIn(".step-io-grid", css)
        self.assertIn(".raw-event", css)

    def test_v0_4_viewer_explains_task_entry_and_round_flow(self) -> None:
        css = (ROOT / "web" / "trace_viewer.css").read_text(encoding="utf-8")
        source = (ROOT / "web" / "trace_viewer.js").read_text(encoding="utf-8")

        self.assertIn("function runStartedEvent", source)
        self.assertIn("function renderTaskEntryItem", source)
        self.assertIn("function renderTaskEntryDetail", source)
        self.assertIn("function renderFlowOverview", source)
        self.assertIn("function buildFlowItems", source)
        self.assertIn("任务入口", source)
        self.assertIn("本轮流程", source)
        self.assertIn("Tool:", source)
        self.assertIn("Final Answer", source)
        self.assertIn("Complete", source)
        self.assertIn(".task-entry", css)
        self.assertIn(".flow-overview", css)
        self.assertIn(".flow-node", css)

    def test_v0_4_viewer_explains_task_completion_separately(self) -> None:
        css = (ROOT / "web" / "trace_viewer.css").read_text(encoding="utf-8")
        source = (ROOT / "web" / "trace_viewer.js").read_text(encoding="utf-8")

        self.assertIn("function terminalEvent", source)
        self.assertIn("function renderTaskCompletionItem", source)
        self.assertIn("function renderTaskCompletionDetail", source)
        self.assertIn("任务完成", source)
        self.assertIn("Run Completed", source)
        self.assertIn("run_completed", source)
        self.assertIn("run_failed", source)
        self.assertIn("task-completion", source)
        self.assertIn(".task-completion", css)


    def test_v0_5_viewer_handles_permission_phases(self) -> None:
        source = (ROOT / "web" / "trace_viewer.js").read_text(encoding="utf-8")

        self.assertIn("permission_requested", source)
        self.assertIn("permission_resolved", source)
        self.assertIn("Permission Request", source)
        self.assertIn("User Approved", source)
        self.assertIn("User Rejected", source)
        self.assertIn('"tool_started"', source)
        self.assertIn("event.input?.tool_name", source)

    def test_v0_5_permission_events_do_not_start_rounds(self) -> None:
        source = (ROOT / "web" / "trace_viewer.js").read_text(encoding="utf-8")

        build_rounds_start = source.index("function buildRounds")
        build_rounds_end = source.index("function enrichRound", build_rounds_start)
        build_rounds_body = source[build_rounds_start:build_rounds_end]

        phases_that_start_rounds = ["context_built"]
        for phase in phases_that_start_rounds:
            self.assertIn(phase, build_rounds_body)

        phases_that_do_not_start_rounds = [
            "permission_requested",
            "permission_resolved",
            "run_started",
            "run_completed",
            "run_failed",
            "run_interrupted",
        ]
        phase_check_lines = [
            line.strip()
            for line in build_rounds_body.splitlines()
            if line.strip().startswith('if (event.phase === "')
        ]
        starting_phases = [
            line.split('"')[1]
            for line in phase_check_lines
        ]
        for phase in phases_that_do_not_start_rounds:
            self.assertNotIn(phase, starting_phases)

    def test_v0_5_preserves_existing_v4_structure_tokens(self) -> None:
        source = (ROOT / "web" / "trace_viewer.js").read_text(encoding="utf-8")
        html = (ROOT / "web" / "trace_viewer.html").read_text(encoding="utf-8")
        css = (ROOT / "web" / "trace_viewer.css").read_text(encoding="utf-8")

        v0_4_tokens = [
            "task-entry",
            "task-completion",
            "flow-overview",
            "summary-panel",
            "context-panel",
            "round-index",
            "round-status-dot",
            "round-step-count",
            "step-io-grid",
            "raw-event",
            "flow-node",
        ]

        for token in v0_4_tokens:
            found = token in source or token in html or token in css
            self.assertTrue(found, f"V0.4 token '{token}' no longer present after V0.5 changes")

    def test_v0_5_does_not_add_approve_reject_buttons(self) -> None:
        html = (ROOT / "web" / "trace_viewer.html").read_text(encoding="utf-8")
        source = (ROOT / "web" / "trace_viewer.js").read_text(encoding="utf-8")

        forbidden = [
            "onclick=\"approve",
            "onclick=\"reject",
            "onclick='approve",
            "onclick='reject",
            "approveButton",
            "rejectButton",
            "id=\"approve",
            "id=\"reject",
        ]
        for token in forbidden:
            self.assertNotIn(token, html.lower())
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
