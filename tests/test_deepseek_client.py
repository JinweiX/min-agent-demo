from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Union
from urllib.error import HTTPError, URLError


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class FakeResponse:
    def __init__(self, payload: Union[dict, str]) -> None:
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
    def __init__(self, payload: Union[dict, str]) -> None:
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


class TimeoutOpener:
    def open(self, request, timeout=30):
        raise TimeoutError("timed out")


class DeepSeekClientTest(unittest.TestCase):
    def test_create_chat_completion_sends_expected_request(self) -> None:
        from min_agent.deepseek_client import DeepSeekClient

        opener = FakeOpener(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"kind":"final_answer","message":"ok","reason":"done","success":true}'
                        }
                    }
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
        self.assertEqual(content, '{"kind":"final_answer","message":"ok","reason":"done","success":true}')
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

    def test_timeout_raises_safe_client_error(self) -> None:
        from min_agent.deepseek_client import DeepSeekClient, ModelClientError

        client = DeepSeekClient(api_key="secret-key", model="deepseek-v4-flash", opener=TimeoutOpener())

        with self.assertRaises(ModelClientError) as caught:
            client.create_chat_completion("system json", "user input")

        self.assertIn("timed out", str(caught.exception))
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
