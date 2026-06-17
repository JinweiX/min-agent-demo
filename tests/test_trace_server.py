from __future__ import annotations

import sys
import urllib.request
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class TraceServerTest(unittest.TestCase):
    def test_server_exposes_url_before_start(self) -> None:
        from min_agent.trace_recorder import TraceRecorder
        from min_agent.trace_server import TraceServer

        recorder = TraceRecorder(user_goal="goal", workspace="workspace")
        server = TraceServer(recorder=recorder, web_dir=ROOT / "web", preferred_port=0)
        try:
            self.assertTrue(server.url.startswith("http://127.0.0.1:"))
        finally:
            server.close()

    def test_server_start_and_stop(self) -> None:
        from min_agent.trace_recorder import TraceRecorder
        from min_agent.trace_server import TraceServer

        recorder = TraceRecorder(user_goal="goal", workspace="workspace")
        server = TraceServer(recorder=recorder, web_dir=ROOT / "web", preferred_port=0)
        server.start()
        try:
            self.assertTrue(server.is_running)
        finally:
            server.stop()

        self.assertFalse(server.is_running)

    def test_server_stops_with_active_events_client(self) -> None:
        from min_agent.trace_recorder import TraceRecorder
        from min_agent.trace_server import TraceServer

        recorder = TraceRecorder(user_goal="goal", workspace="workspace")
        server = TraceServer(recorder=recorder, web_dir=ROOT / "web", preferred_port=0)

        server.start()
        response = urllib.request.urlopen(server.url + "events", timeout=2)
        try:
            server.stop()
            self.assertFalse(server.is_running)
        finally:
            response.close()
            server.close()


if __name__ == "__main__":
    unittest.main()
