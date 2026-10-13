"""Tavily web-search retriever.

Talks to the Tavily REST API (``POST {base_url}/search``) using httpx.  The
API key comes from configuration (populated from the ``TAVILY_API_KEY``
environment variable) and is never logged or embedded in evidence.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from app.falsify.config import RetrievalConfig
from app.falsify.exceptions import ConfigurationError, RetrieverUnavailableError
from app.falsify.logging_utils import log_event
from app.falsify.models import Evidence
from app.falsify.retrieval.base import extract_domain


class TavilyRetriever:
    """EvidenceRetriever implementation backed by Tavily search."""

    def __init__(self, config: RetrievalConfig | None = None, api_key: str | None = None) -> None:
        self._config = config or RetrievalConfig.from_env()
        key = api_key or self._config.api_key
        if not key:
            raise ConfigurationError(
                "TavilyRetriever requires an API key (set the TAVILY_API_KEY environment variable)"
            )
        self._api_key = key

    @property
    def name(self) -> str:
        return "tavily"

    def search(self, query: str, *, max_results: int = 5) -> list[Evidence]:
        payload: dict[str, Any] = {
            "api_key": self._api_key,
            "query": query,
            "search_depth": "basic",
            "include_answer": False,
            "include_raw_content": False,
            "max_results": max_results,
        }
        url = self._config.base_url.rstrip("/") + "/search"
        try:
            response = httpx.post(url, json=payload, timeout=self._config.request_timeout_s)
        except httpx.HTTPError as exc:
            raise RetrieverUnavailableError(f"Tavily request failed: {exc}") from exc

        if response.status_code in (401, 403):
            raise RetrieverUnavailableError("Tavily authentication failed (invalid API key)")
        if response.status_code == 429:
            raise RetrieverUnavailableError("Tavily rate limit exceeded")
        if response.status_code >= 400:
            raise RetrieverUnavailableError(
                f"Tavily returned HTTP {response.status_code}: {response.text[:200]}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise RetrieverUnavailableError(f"Tavily returned invalid JSON: {exc}") from exc

        results = data.get("results") or []
        evidence: list[Evidence] = []
        now = datetime.now(UTC)
        for item in results[:max_results]:
            if not isinstance(item, dict):
                continue
            source_url = str(item.get("url") or "").strip()
            if not source_url:
                # Never fabricate evidence: skip results without a real URL.
                continue
            evidence.append(
                Evidence(
                    query_id=None,  # filled in by the orchestrator
                    source_url=source_url,
                    title=str(item.get("title") or ""),
                    publisher=str(item.get("name") or item.get("publisher") or ""),
                    domain=extract_domain(source_url),
                    retrieved_text=str(item.get("content") or ""),
                    publication_date=item.get("published_date") or None,
                    retrieval_timestamp=now,
                    score=float(item["score"]) if isinstance(item.get("score"), (int, float)) else None,
                )
            )
        log_event("tavily_search_done", query_len=len(query), results=len(evidence))
        return evidence
