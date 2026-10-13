"""Evidence retrieval abstraction.

The verification engine depends only on the :class:`EvidenceRetriever`
protocol.  Tavily is one implementation; tests and offline demos can inject
any other provider.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.falsify.models import Evidence


@runtime_checkable
class EvidenceRetriever(Protocol):
    """Anything that can turn a search query into evidence items."""

    def search(self, query: str, *, max_results: int = 5) -> list[Evidence]:
        """Return up to ``max_results`` evidence items for ``query``.

        Implementations should raise
        :class:`app.falsify.exceptions.RetrieverUnavailableError` when the
        provider cannot be reached; the orchestrator records that as a
        structured retrieval failure and continues.
        """
        ...

    @property
    def name(self) -> str:
        """Provider name for result metadata / logs."""
        ...


def extract_domain(url: str) -> str:
    """Best-effort domain extraction without requiring urllib.parse everywhere."""
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
        domain = (parsed.netloc or url).lower()
        return domain.removeprefix("www.")
    except ValueError:
        return ""
