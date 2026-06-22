from __future__ import annotations

import json
import urllib.request
from typing import Any, Optional
from urllib.error import HTTPError, URLError


class ModelClientError(Exception):
    pass


class DeepSeekClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.deepseek.com",
        timeout_seconds: float = 30,
        max_tokens: int = 1200,
        opener: Optional[Any] = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.opener = opener or urllib.request.build_opener()

    def create_chat_completion(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        request = urllib.request.Request(
            url=f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with self.opener.open(request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise ModelClientError(f"DeepSeek request failed with HTTP {exc.code}") from exc
        except URLError as exc:
            raise ModelClientError(f"DeepSeek request failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise ModelClientError(f"DeepSeek request timed out: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ModelClientError("DeepSeek response was not valid JSON") from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelClientError("DeepSeek response missing message content") from exc

        if not isinstance(content, str):
            raise ModelClientError("DeepSeek response message content is not a string")
        if not content.strip():
            raise ModelClientError("DeepSeek response empty message content")
        return content
