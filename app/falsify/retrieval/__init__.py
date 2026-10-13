from app.falsify.retrieval.base import EvidenceRetriever, extract_domain
from app.falsify.retrieval.mock import InMemoryRetriever
from app.falsify.retrieval.tavily import TavilyRetriever

__all__ = ["EvidenceRetriever", "TavilyRetriever", "InMemoryRetriever", "extract_domain"]


def build_retriever_from_config(config) -> EvidenceRetriever:
    """Factory used by :func:`app.falsify.engine.build_default_engine`.

    Falls back to an *empty* in-memory retriever when no Tavily key is
    configured, so the pipeline degrades to UNVERIFIABLE instead of crashing.
    """
    from app.falsify.config import RetrievalConfig
    from app.falsify.logging_utils import log_event

    assert isinstance(config, RetrievalConfig)
    if config.provider == "tavily" and config.api_key:
        return TavilyRetriever(config)
    log_event("retrieval_disabled", reason="missing_tavily_api_key", level=30)
    return InMemoryRetriever([], name="none")
