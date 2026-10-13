"""Concrete LLM providers.

* :class:`OpenAICompatLLM` -- works with any OpenAI-compatible chat API
  (OpenAI, Nebius AI Studio, NVIDIA NIM, vLLM, Together, ...).  Configured
  exclusively via :class:`app.falsify.config.LLMConfig`; API keys come from
  environment variables and are never logged.
* :class:`NullLLM` -- explicit "no LLM" provider.  The engine degrades to
  its deterministic pipeline, which remains fully functional.
* :class:`MockLLM` -- scripted responses for tests and offline demos.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable

from app.falsify.config import LLMConfig
from app.falsify.exceptions import LLMUnavailableError
from app.falsify.logging_utils import log_event


class OpenAICompatLLM:
    """Synchronous client for OpenAI-compatible ``/chat/completions`` APIs."""

    def __init__(self, config: LLMConfig) -> None:
        if not config.api_key:
            raise LLMUnavailableError(
                "OpenAICompatLLM requires an API key (set LLM_API_KEY / NEBIUS_API_KEY)"
            )
        self._config = config

    @property
    def name(self) -> str:
        return f"openai_compat:{self._config.model}"

    def generate(self, prompt: str, *, system: str | None = None, max_tokens: int | None = None) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self._config.model,
            "messages": messages,
            "temperature": self._config.temperature,
            "max_tokens": max_tokens or self._config.max_tokens,
        }
        url = self._config.base_url.rstrip("/") + "/chat/completions"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                # The key goes into the header only -- never into logs.
                "Authorization": f"Bearer {self._config.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._config.request_timeout_s) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:  # pragma: no cover - network path
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise LLMUnavailableError(f"LLM HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:  # pragma: no cover
            raise LLMUnavailableError(f"LLM request failed: {exc}") from exc

        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:  # pragma: no cover
            raise LLMUnavailableError(f"Unexpected LLM response shape: {body!r:.300}") from exc
        if not isinstance(content, str):  # pragma: no cover
            raise LLMUnavailableError("LLM response content is not a string")
        return content


class NullLLM:
    """Provider that is always 'unavailable'.

    Injecting this makes the engine run its fully deterministic pipeline --
    useful for tests, air-gapped environments and as the graceful degradation
    path when no LLM credentials are configured.
    """

    @property
    def name(self) -> str:
        return "null"

    def generate(self, prompt: str, *, system: str | None = None, max_tokens: int | None = None) -> str:
        raise LLMUnavailableError("No LLM provider configured (NullLLM)")


class MockLLM:
    """Scripted LLM for tests and offline demos.

    ``responses`` may map a substring of the prompt to a canned reply, or be
    a callable ``(prompt) -> str``.  Unmatched prompts raise
    :class:`LLMUnavailableError` so tests can assert fallback behaviour.
    """

    def __init__(
        self,
        responses: dict[str, str] | Callable[[str], str] | None = None,
        name: str = "mock",
    ) -> None:
        self._responses = responses or {}
        self._name = name
        self.calls: list[str] = []

    @property
    def name(self) -> str:
        return self._name

    def generate(self, prompt: str, *, system: str | None = None, max_tokens: int | None = None) -> str:
        self.calls.append(prompt)
        if callable(self._responses):
            return self._responses(prompt)
        for needle, reply in self._responses.items():
            if needle in prompt:
                return reply
        raise LLMUnavailableError(f"MockLLM has no scripted response for prompt starting {prompt[:80]!r}")


def build_llm_from_config(config: LLMConfig):
    """Factory used by :func:`app.falsify.engine.build_default_engine`."""
    if config.provider == "none":
        log_event("llm_disabled", reason="provider=none")
        return NullLLM()
    if not config.api_key:
        log_event("llm_disabled", reason="missing_api_key", level=20)
        return NullLLM()
    try:
        llm = OpenAICompatLLM(config)
    except LLMUnavailableError as exc:
        log_event("llm_disabled", reason=str(exc), level=30)
        return NullLLM()
    log_event("llm_enabled", provider=llm.name)
    return llm
