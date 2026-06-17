from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class TraceRecorderTest(unittest.TestCase):
    def test_emit_increments_steps_and_notifies_subscribers(self) -> None:
        from min_agent.trace_recorder import TraceRecorder

        received = []
        recorder = TraceRecorder(user_goal="goal", workspace="workspace")
        recorder.subscribe(received.append)

        event = recorder.emit(
            phase="run_started",
            status="running",
            title="收到任务",
            reason="用户提交任务",
        )

        self.assertEqual(event.step, 1)
        self.assertEqual(received[0], event)

    def test_save_writes_json_run_record(self) -> None:
        from min_agent.trace_recorder import TraceRecorder

        with tempfile.TemporaryDirectory() as tmp:
            recorder = TraceRecorder(user_goal="goal", workspace="workspace")
            recorder.emit("run_started", "running", "收到任务")
            path = recorder.save(Path(tmp), status="completed")

            data = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["user_goal"], "goal")
        self.assertEqual(len(data["events"]), 1)


if __name__ == "__main__":
    unittest.main()
