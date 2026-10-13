"""Structured logging helpers.

Emits machine-parseable ``event=<name> key=value ...`` lines through the
standard ``logging`` module.  Sensitive material (API keys, full evidence
bodies) is never logged -- only counts, ids and short labels.
"""

from __future__ import annotations

import logging
from typing import Any

LOGGER_NAME = "falsify"

logger = logging.getLogger(LOGGER_NAME)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)
logger.propagate = False


def _fmt_value(value: Any) -> str:
    if isinstance(value, str):
        # quote values containing spaces; never allow newlines to break the event line
        sanitized = value.replace("\n", " ").replace("\r", " ")
        if len(sanitized) > 200:
            sanitized = sanitized[:197] + "..."
        return f'"{sanitized}"' if (" " in sanitized or '"' in sanitized) else sanitized
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def log_event(event: str, level: int = logging.INFO, **fields: Any) -> None:
    """Log a structured pipeline event, e.g. ``log_event("queries_generated", n=7)``."""
    parts = " ".join(f"{k}={_fmt_value(v)}" for k, v in fields.items())
    logger.log(level, "event=%s %s", event, parts)
