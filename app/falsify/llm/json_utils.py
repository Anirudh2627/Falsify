"""Robust JSON extraction helpers for LLM output.

LLMs frequently wrap JSON in prose or code fences.  These helpers extract and
repair JSON payloads deterministically and raise
:class:`MalformedLLMResponseError` when nothing usable is found -- the caller
then falls back to deterministic logic instead of trusting garbage.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.falsify.exceptions import MalformedLLMResponseError

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(raw: str) -> Any:
    """Extract the first JSON object/array from an LLM response.

    Tries, in order: direct parse, code-fence contents, first balanced
    ``{...}`` or ``[...]`` span (with simple trailing-comma repair).
    """
    if raw is None:
        raise MalformedLLMResponseError("LLM returned no content")
    text = raw.strip()
    if not text:
        raise MalformedLLMResponseError("LLM returned empty content")

    # 1) direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2) fenced block
    for match in _FENCE_RE.finditer(text):
        candidate = match.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            repaired = _repair(candidate)
            if repaired is not None:
                return repaired

    # 3) first balanced span
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        while start != -1:
            span = _balanced_span(text, start, opener, closer)
            if span is not None:
                try:
                    return json.loads(span)
                except json.JSONDecodeError:
                    repaired = _repair(span)
                    if repaired is not None:
                        return repaired
            start = text.find(opener, start + 1)

    raise MalformedLLMResponseError(f"No JSON payload found in LLM response: {text[:200]!r}")


def _balanced_span(text: str, start: int, opener: str, closer: str) -> str | None:
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _repair(candidate: str) -> Any | None:
    """Best-effort repair: strip trailing commas, normalize smart quotes."""
    fixed = re.sub(r",\s*([}\]])", r"\1", candidate)
    fixed = fixed.replace("\u201c", '"').replace("\u201d", '"')
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        return None
