"""LLM provider abstraction.

The verification engine never hard-codes a specific LLM.  Components depend
on the :class:`LLMProvider` protocol; concrete providers are injected.

:func:`generate_json` is the shared helper all pipeline stages use: it calls
the provider, extracts/repairs JSON, and RETRIES on malformed output (per
the failure-handling spec) before giving up -- callers then fall back to
their deterministic logic.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal synchronous LLM interface used across the pipeline."""

    def generate(self, prompt: str, *, system: str | None = None, max_tokens: int | None = None) -> str:
        """Return the model completion for ``prompt``.

        Implementations should raise :class:`app.falsify.exceptions.LLMUnavailableError`
        when the model cannot be reached.  Callers treat LLM output as
        *advisory* and must validate it before use.
        """
        ...

    @property
    def name(self) -> str:
        """Human-readable provider name (for logs / result metadata)."""
        ...


def generate_json(
    llm: LLMProvider,
    prompt: str,
    *,
    system: str | None = None,
    max_retries: int = 2,
    stage: str = "llm",
) -> Any:
    """Call ``llm`` and parse JSON, retrying on malformed responses.

    Makes at most ``max_retries + 1`` attempts.  Retries only happen for
    malformed output; :class:`LLMUnavailableError` propagates immediately
    (callers degrade to deterministic logic).  Raises
    :class:`MalformedLLMResponseError` when all attempts fail.
    """
    from app.falsify.exceptions import MalformedLLMResponseError
    from app.falsify.llm.json_utils import extract_json
    from app.falsify.logging_utils import log_event

    last_error: MalformedLLMResponseError | None = None
    for attempt in range(max(0, max_retries) + 1):
        raw = llm.generate(prompt, system=system)
        try:
            return extract_json(raw)
        except MalformedLLMResponseError as exc:
            last_error = exc
            if attempt < max_retries:
                log_event(
                    "llm_response_retry",
                    stage=stage,
                    attempt=attempt + 1,
                    reason=str(exc)[:140],
                    level=30,
                )
    assert last_error is not None
    raise last_error
