from __future__ import annotations

import json
import mimetypes
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from min_agent.trace_recorder import TraceRecorder
from min_agent.types import TraceEvent


class TraceHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False


class TraceServer:
    def __init__(self, recorder: TraceRecorder, web_dir: Path, preferred_port: int = 8765) -> None:
        self.recorder = recorder
        self.web_dir = web_dir.resolve()
        self._queues: list[queue.Queue[TraceEvent | None]] = []
        self._queues_lock = threading.Lock()
        self._closing = False
        self._server = self._make_server(preferred_port)
        self._thread: threading.Thread | None = None
        self.is_running = False
        self.recorder.subscribe(self._broadcast)

    @property
    def url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}/"

    def start(self) -> None:
        if self.is_running:
            return
        self._closing = False
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self.is_running = True

    def stop(self) -> None:
        if not self.is_running:
            return
        self._closing = True
        self._close_event_streams()
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self.is_running = False

    def close(self) -> None:
        if self.is_running:
            self.stop()
            return
        self._closing = True
        self._close_event_streams()
        self._server.server_close()

    def _broadcast(self, event: TraceEvent) -> None:
        with self._queues_lock:
            queues = list(self._queues)
        for event_queue in queues:
            event_queue.put(event)

    def _close_event_streams(self) -> None:
        with self._queues_lock:
            queues = list(self._queues)
        for event_queue in queues:
            event_queue.put(None)

    def _make_server(self, preferred_port: int) -> ThreadingHTTPServer:
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path == "/events":
                    self._handle_events()
                    return
                self._handle_static()

            def log_message(self, format: str, *args: object) -> None:
                return

            def _handle_static(self) -> None:
                relative = "trace_viewer.html" if self.path in {"/", "/index.html"} else self.path.lstrip("/")
                file_path = (outer.web_dir / relative).resolve()
                if not file_path.is_relative_to(outer.web_dir) or not file_path.exists():
                    self.send_error(404)
                    return
                if not file_path.is_file():
                    self.send_error(404)
                    return

                content = file_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", mimetypes.guess_type(file_path.name)[0] or "application/octet-stream")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)

            def _handle_events(self) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()

                event_queue: queue.Queue[TraceEvent | None] = queue.Queue()
                with outer._queues_lock:
                    outer._queues.append(event_queue)
                try:
                    for event in outer.recorder.history():
                        self._write_event(event)
                    while not outer._closing:
                        event = event_queue.get()
                        if event is None:
                            break
                        self._write_event(event)
                except (BrokenPipeError, ConnectionResetError):
                    return
                finally:
                    with outer._queues_lock:
                        if event_queue in outer._queues:
                            outer._queues.remove(event_queue)

            def _write_event(self, event: TraceEvent) -> None:
                payload = json.dumps(event.to_dict(), ensure_ascii=False)
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()

        ports = [preferred_port] if preferred_port == 0 else list(range(preferred_port, preferred_port + 20))
        last_error: OSError | None = None
        for port in ports:
            try:
                return TraceHTTPServer(("127.0.0.1", port), Handler)
            except OSError as exc:
                last_error = exc
        raise OSError(f"could not bind trace server: {last_error}")
