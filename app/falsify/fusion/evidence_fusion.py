"""Evidence fusion.

Aggregates assessed evidence into a decision-ready summary while defending
against the classic failure mode: *three low-quality sites copying the same
wrong statement must not outweigh one authoritative primary source*.

Mechanisms:
* **De-duplication / correlation** -- evidence with (near-)identical text or
  the same normalized URL is collapsed into a single *cluster*; a cluster
  counts as ONE independent voice regardless of how many copies exist.
* **Weighting** -- each item is weighted by relevance, source quality and
  temporal validity; a cluster contributes its *max* member weight (copies
  do not accumulate).
* **Coverage** -- how many falsification hypotheses actually attracted
  relevant evidence.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from app.falsify.config import EngineConfig
from app.falsify.logging_utils import log_event
from app.falsify.models import (
    Claim,
    Evidence,
    EvidenceAssessment,
    EvidenceCluster,
    FalsificationHypothesis,
    FusionSummary,
    SearchQuery,
)

_TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid", "igshid", "yclid", "msclkid", "dclid"}


def normalize_url(url: str) -> str:
    """Canonicalize a URL for duplicate detection (scheme/host/path, sorted params,
    tracking parameters stripped)."""
    try:
        parsed = urlparse(url.strip())
        host = (parsed.netloc or "").lower().removeprefix("www.")
        path = re.sub(r"/+$", "", parsed.path.lower())
        params = urlencode(
            sorted((k, v) for k, v in parse_qsl(parsed.query) if not k.lower().startswith("utm_") and k.lower() not in _TRACKING_PARAMS)
        )
        return urlunparse((parsed.scheme.lower() or "https", host, path, "", params, ""))
    except ValueError:
        return url.strip().lower()


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", text.lower()))


def text_similarity(a: str, b: str) -> float:
    """Token-level Jaccard similarity, used to detect syndicated copies."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


class EvidenceFusion:
    """Fuses per-item assessments into an aggregate picture."""

    def __init__(self, config: EngineConfig | None = None) -> None:
        self._config = config or EngineConfig()

    def fuse(
        self,
        *,
        claim: Claim,
        hypotheses: list[FalsificationHypothesis],
        queries: list[SearchQuery],
        evidence: list[Evidence],
        assessments: list[EvidenceAssessment],
        retrieval_failures: int = 0,
        relevant_ids_by_query: dict[str, set[str]] | None = None,
    ) -> tuple[FusionSummary, list[EvidenceCluster]]:
        assessment_by_id = {a.evidence_id: a for a in assessments}
        pairs = [(ev, assessment_by_id[ev.evidence_id]) for ev in evidence if ev.evidence_id in assessment_by_id]

        # ---- weights -------------------------------------------------------
        weights: dict[str, float] = {}
        for ev, assessment in pairs:
            weights[ev.evidence_id] = self._weight(assessment)

        # ---- clustering (union-find) ---------------------------------------
        parent: dict[str, str] = {ev.evidence_id: ev.evidence_id for ev, _ in pairs}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        by_url: dict[str, str] = {}
        for ev, _ in pairs:
            key = normalize_url(ev.source_url)
            if key in by_url:
                union(by_url[key], ev.evidence_id)
            else:
                by_url[key] = ev.evidence_id

        items = [ev for ev, _ in pairs]
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = items[i], items[j]
                if find(a.evidence_id) == find(b.evidence_id):
                    continue
                sim = text_similarity(
                    f"{a.title} {a.retrieved_text}", f"{b.title} {b.retrieved_text}"
                )
                threshold = self._config.duplicate_text_similarity
                if a.domain and a.domain == b.domain:
                    threshold = min(threshold, 0.5)  # same-site repetition counts as one voice earlier
                if sim >= threshold:
                    union(a.evidence_id, b.evidence_id)

        clusters_map: dict[str, list[Evidence]] = {}
        for ev, _ in pairs:
            clusters_map.setdefault(find(ev.evidence_id), []).append(ev)

        clusters: list[EvidenceCluster] = []
        for members in clusters_map.values():
            # cluster stance = stance of its strongest member; weight = max member weight
            strongest = max(members, key=lambda m: weights.get(m.evidence_id, 0.0))
            assessment = assessment_by_id[strongest.evidence_id]
            clusters.append(
                EvidenceCluster(
                    evidence_ids=[m.evidence_id for m in members],
                    representative_domain=strongest.domain or normalize_url(strongest.source_url),
                    stance=assessment.stance,
                    weight=round(max(weights.get(m.evidence_id, 0.0) for m in members), 4),
                )
            )

        # ---- aggregate ------------------------------------------------------
        support_strength = sum(c.weight for c in clusters if c.stance == "supporting")
        contradict_strength = sum(c.weight for c in clusters if c.stance == "contradicting")
        supporting_items = [ev for ev, a in pairs if a.stance == "supporting"]
        contradicting_items = [ev for ev, a in pairs if a.stance == "contradicting"]

        max_support_quality = max((assessment_by_id[e.evidence_id].source_quality_score for e in supporting_items), default=0.0)
        max_contradict_quality = max((assessment_by_id[e.evidence_id].source_quality_score for e in contradicting_items), default=0.0)

        # coverage: hypotheses that attracted at least one relevant evidence item
        query_to_hypothesis = {q.query_id: q.hypothesis_id for q in queries}
        relevant_evidence_ids = {a.evidence_id for a in assessments if a.relevance_score >= self._config.relevance_floor}
        if relevant_ids_by_query is not None:
            # engine-provided map counts evidence returned to a query even when the
            # same URL was already kept under an earlier query (de-duplicated)
            hypotheses_with_evidence = {
                query_to_hypothesis.get(qid)
                for qid, ids in relevant_ids_by_query.items()
                if ids and qid in query_to_hypothesis
            }
        else:
            hypotheses_with_evidence = {
                query_to_hypothesis.get(ev.query_id or "")
                for ev in evidence
                if ev.evidence_id in relevant_evidence_ids and ev.query_id in query_to_hypothesis
            }
        hypotheses_with_evidence.discard(None)
        coverage = (len(hypotheses_with_evidence) / len(hypotheses)) if hypotheses else 0.0

        summary = FusionSummary(
            supporting_evidence=len(supporting_items),
            contradicting_evidence=len(contradicting_items),
            neutral_evidence=len(pairs) - len(supporting_items) - len(contradicting_items),
            total_evidence=len(pairs),
            independent_supporting_clusters=sum(1 for c in clusters if c.stance == "supporting"),
            independent_contradicting_clusters=sum(1 for c in clusters if c.stance == "contradicting"),
            support_strength=round(support_strength, 4),
            contradict_strength=round(contradict_strength, 4),
            max_support_quality=round(max_support_quality, 3),
            max_contradict_quality=round(max_contradict_quality, 3),
            duplicated_evidence_detected=len(pairs) - len(clusters),
            hypotheses_total=len(hypotheses),
            hypotheses_with_evidence=len(hypotheses_with_evidence),
            coverage=round(coverage, 3),
            retrieval_failures=retrieval_failures,
        )
        log_event(
            "evidence_fused",
            clusters=len(clusters),
            support=round(support_strength, 3),
            contradict=round(contradict_strength, 3),
            duplicates=summary.duplicated_evidence_detected,
            coverage=summary.coverage,
        )
        return summary, clusters

    def _weight(self, assessment: EvidenceAssessment) -> float:
        relevance = assessment.relevance_score
        if relevance < self._config.relevance_floor:
            return 0.0
        quality_factor = 0.4 + 0.6 * assessment.source_quality_score
        temporal_factor = 0.5 + 0.5 * assessment.temporal_validity
        direct_bonus = 0.05 if assessment.is_direct else 0.0
        return round(min(1.0, relevance * quality_factor * temporal_factor + direct_bonus), 4)
