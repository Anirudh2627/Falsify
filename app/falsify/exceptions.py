"""Meaningful exceptions for the Falsify engine.

Design rule: *expected* external failures (retrieval down, LLM down,
malformed model output) are handled gracefully inside the pipeline and
recorded as structured :class:`app.falsify.models.PipelineError` entries.
Exceptions here are raised for genuinely invalid usage or unrecoverable
programming errors.
"""

from __future__ import annotations


class FalsifyError(Exception):
    """Base class for all Falsify errors."""


class ClaimValidationError(FalsifyError):
    """The input claim is unusable (empty, too long, non-text)."""


class ConfigurationError(FalsifyError):
    """The engine was configured incorrectly (e.g. provider selected without credentials)."""


class LLMError(FalsifyError):
    """Base class for LLM provider failures."""


class LLMUnavailableError(LLMError):
    """The LLM provider could not be reached or refused the request."""


class MalformedLLMResponseError(LLMError):
    """The LLM produced output that could not be parsed into the expected schema."""


class RetrievalError(FalsifyError):
    """Base class for evidence retrieval failures."""


class RetrieverUnavailableError(RetrievalError):
    """The retrieval provider could not be reached (network / auth / quota)."""
