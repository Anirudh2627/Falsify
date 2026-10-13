"""In-memory retriever for tests and offline demos.

This is *test infrastructure*, not production retrieval: it returns the
fixtures it was constructed with, matched against queries by keyword
overlap.  Production code never instantiates this class.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.falsify.exceptions import RetrieverUnavailableError
from app.falsify.models import Evidence


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9%$]+", text.lower()))


class InMemoryRetriever:
    """Deterministic, offline EvidenceRetriever backed by a fixture corpus."""

    def __init__(
        self,
        corpus: Sequence[Evidence],
        *,
        name: str = "in_memory",
        fail_with: Exception | None = None,
        min_overlap: int = 1,
    ) -> None:
        self._corpus = list(corpus)
        self._name = name
        self._fail_with = fail_with
        self._min_overlap = min_overlap
        self.queries: list[str] = []

    @property
    def name(self) -> str:
        return self._name

    def add(self, evidence: Evidence) -> None:
        self._corpus.append(evidence)

    def search(self, query: str, *, max_results: int = 5) -> list[Evidence]:
        self.queries.append(query)
        if self._fail_with is not None:
            raise self._fail_with if isinstance(self._fail_with, RetrieverUnavailableError) else RetrieverUnavailableError(str(self._fail_with))
        query_words = _words(query)
        scored: list[tuple[int, Evidence]] = []
        for item in self._corpus:
            doc_words = _words(f"{item.title} {item.retrieved_text} {' '.join(item.relevant_passages)}")
            overlap = len(query_words & doc_words)
            if overlap >= self._min_overlap:
                scored.append((overlap, item))
        scored.sort(key=lambda pair: (-pair[0], pair[1].evidence_id))
        return [item.model_copy(deep=True) for _, item in scored[:max_results]]
