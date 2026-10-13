"""Adversarial search query generation.

Queries are derived from falsification hypotheses -- they are deliberately
designed to surface evidence AGAINST the claim (primary documents,
contradictory figures, alternative interpretations, newer corrections,
independent reporting), never just to re-search the claim itself.
"""

from __future__ import annotations

import re

from app.falsify.config import EngineConfig
from app.falsify.exceptions import LLMError
from app.falsify.llm.base import LLMProvider
from app.falsify.llm.provider import NullLLM
from app.falsify.logging_utils import log_event
from app.falsify.models import Claim, ClaimKind, FalsificationHypothesis, HypothesisCategory, QueryType, SearchQuery
from app.falsify.prompts import queries as prompts

_STOPWORDS = {
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "by", "with", "was", "were",
    "is", "are", "be", "been", "has", "have", "had", "it", "its", "that", "this",
    "than", "from", "and", "or", "as", "about", "into", "over", "after", "before",
    "increased", "decreased", "grew", "declined", "rose", "fell", "will", "would",
}


class AdversarialQueryGenerator:
    """Generates falsification-oriented search queries for a hypothesis."""

    def __init__(self, config: EngineConfig | None = None, llm: LLMProvider | None = None) -> None:
        self._config = config or EngineConfig()
        self._llm = llm

    def generate(
        self,
        claim: Claim,
        hypothesis: FalsificationHypothesis,
        *,
        exclude: set[str] | None = None,
    ) -> list[SearchQuery]:
        """Generate queries for one hypothesis.

        ``exclude`` is a set of already-used (lowercased) query strings so the
        orchestrator can dedupe across hypotheses.
        """
        exclude = {q.lower() for q in (exclude or set())}
        candidates = self._generate_deterministic(claim, hypothesis)

        if self._llm is not None and not isinstance(self._llm, NullLLM) and self._config.use_llm_for_queries:
            llm_candidates = self._generate_with_llm(claim, hypothesis)
            if llm_candidates:
                # reserve at least one slot for LLM-designed queries so the call
                # is never wasted behind deterministic templates
                reserved = max(1, self._config.max_queries_per_hypothesis - 1)
                candidates = candidates[:reserved] + llm_candidates + candidates[reserved:]

        # dedupe, cap
        seen: set[str] = set()
        out: list[SearchQuery] = []
        for query, qtype, rationale in candidates:
            normalized = self._clean(query)
            key = normalized.lower()
            if not normalized or key in seen or key in exclude:
                continue
            seen.add(key)
            out.append(
                SearchQuery(
                    hypothesis_id=hypothesis.hypothesis_id,
                    claim_id=claim.claim_id,
                    query=normalized,
                    query_type=qtype,
                    rationale=rationale,
                )
            )
            if len(out) >= self._config.max_queries_per_hypothesis:
                break
        return out

    @staticmethod
    def _clean(query: str) -> str:
        query = re.sub(r"\s+", " ", query).strip()
        return query

    # ------------------------------------------------------------------
    # Deterministic templates
    # ------------------------------------------------------------------

    def _generate_deterministic(
        self, claim: Claim, hypothesis: FalsificationHypothesis
    ) -> list[tuple[str, QueryType, str]]:
        q = claim.primary_quantity
        entity = claim.primary_entity or ""
        metric = (q.metric if q and q.metric else "") or ""
        period = claim.temporal_constraints[0] if claim.temporal_constraints else ""
        value = (q.raw_value if q else "") or ""
        baseline = (q.comparison_baseline if q and q.comparison_baseline else "") or ""
        category = hypothesis.category

        slots = [s for s in (entity, metric, period) if s]
        subject = " ".join(slots) if slots else self._keyword_fallback(claim)

        cands: list[tuple[str, QueryType, str]] = []

        if claim.claim_kind in (ClaimKind.QUANTITATIVE_CHANGE, ClaimKind.QUANTITATIVE_STATE) and entity:
            if category == HypothesisCategory.NUMERICAL:
                cands += [
                    (f"{entity} {metric} {period} actual reported figure", QueryType.PRIMARY_SOURCE,
                     "Find the authoritative number to compare against the claimed value."),
                    (f"{entity} {metric} decline {period}", QueryType.CONTRADICTION,
                     "Search specifically for evidence of the opposite direction."),
                    (f"{entity} {metric} {period} compared with {baseline or 'previous year'}", QueryType.PRIMARY_SOURCE,
                     "Recompute the change from primary period-over-period figures."),
                    (f"{entity} {metric} {value} {period}", QueryType.CONTRADICTION,
                     "Check whether the exact claimed figure appears in any authoritative source."),
                    (f"{entity} {metric} {period} discrepancy OR restated OR corrected", QueryType.CONTRADICTION,
                     "Surface corrections or disputes about the figure."),
                ]
            elif category == HypothesisCategory.TEMPORAL:
                cands += [
                    (f"{entity} {metric} quarterly results {period}", QueryType.ALTERNATIVE_INTERPRETATION,
                     "Test whether the figure belongs to a quarter rather than the full period."),
                    (f"{entity} fiscal year {metric} {period}", QueryType.PRIMARY_SOURCE,
                     "Fiscal vs calendar year mismatch is a common temporal error."),
                    (f"{entity} {metric} by year history", QueryType.PRIMARY_SOURCE,
                     "A year-by-year history shows which period the figure actually matches."),
                ]
            elif category == HypothesisCategory.DEFINITIONAL:
                cands += [
                    (f"{entity} {metric} GAAP non-GAAP definition {period}", QueryType.ALTERNATIVE_INTERPRETATION,
                     "Different accounting definitions can change the reported growth."),
                    (f"{entity} {metric} definition methodology", QueryType.ALTERNATIVE_INTERPRETATION,
                     "Find how the metric is officially defined."),
                ]
            elif category == HypothesisCategory.SCOPE:
                cands += [
                    (f"{entity} {metric} by segment {period}", QueryType.ALTERNATIVE_INTERPRETATION,
                     "Segment-level figures are often mistaken for company-wide ones."),
                    (f"{entity} {metric} {period} annual vs quarterly", QueryType.ALTERNATIVE_INTERPRETATION,
                     "Test the quarter-vs-year confusion directly."),
                ]
            elif category == HypothesisCategory.SOURCE:
                cands += [
                    (f"{entity} {metric} {period} preliminary results final", QueryType.RECENCY,
                     "Preliminary figures are frequently revised."),
                    (f"{entity} {period} annual report {metric}", QueryType.PRIMARY_SOURCE,
                     "The annual report is the authoritative record."),
                    (f"{entity} {metric} {period} latest news", QueryType.RECENCY,
                     "Newer reporting may supersede the claim's basis."),
                ]
            elif category in (HypothesisCategory.ENTITY, HypothesisCategory.ATTRIBUTION):
                cands += [
                    (f"{entity} {metric} {period} official press release", QueryType.PRIMARY_SOURCE,
                     "The company's own release is the attribution anchor."),
                    (f"{value} {metric} {period} which company", QueryType.CONTRADICTION,
                     "Check whether the figure actually belongs to another entity."),
                ]
            else:  # CAUSAL / generic on a quantitative claim
                cands += [
                    (f"{entity} {metric} {period} analysis", QueryType.INDEPENDENT_REPORTING,
                     "Independent analysis may challenge the framing of the figure."),
                ]

        elif claim.claim_kind == ClaimKind.CAUSAL:
            subj = self._keyword_fallback(claim)
            if category == HypothesisCategory.CAUSAL:
                cands += [
                    (f"{subj} correlation not causation criticism", QueryType.CONTRADICTION,
                     "Search for critiques of the causal link."),
                    (f"{subj} confounding factors study", QueryType.INDEPENDENT_REPORTING,
                     "Confounders would falsify a direct causal reading."),
                    (f"{subj} reverse causation evidence", QueryType.CONTRADICTION,
                     "Reverse causation is a direct falsifier."),
                ]
            else:
                cands += [
                    (f"{subj} evidence study", QueryType.PRIMARY_SOURCE,
                     "Primary studies anchor the causal claim."),
                    (f"{subj} debunked OR disputed OR retracted", QueryType.CONTRADICTION,
                     "Look for challenges to the underlying evidence."),
                ]

        elif claim.claim_kind == ClaimKind.FUTURE:
            subj = self._keyword_fallback(claim)
            cands += [
                (f"{subj} forecast revised OR withdrawn", QueryType.RECENCY,
                 "A revised forecast undermines the claim's basis."),
                (f"{subj} latest projection", QueryType.RECENCY,
                 "The newest authoritative projection is the benchmark."),
                (f"{subj} expert consensus", QueryType.INDEPENDENT_REPORTING,
                 "Consensus divergence weakens a specific projection."),
            ]

        else:  # FACTUAL / COMPARATIVE / ATTRIBUTION / UNKNOWN
            subj = self._keyword_fallback(claim)
            if category == HypothesisCategory.ATTRIBUTION:
                cands += [
                    (f"{subj} full quote transcript primary source", QueryType.PRIMARY_SOURCE,
                     "Locate the primary record of the statement."),
                    (f"{subj} misquote OR out of context", QueryType.CONTRADICTION,
                     "Search directly for misattribution reports."),
                ]
            elif category == HypothesisCategory.ENTITY:
                cands += [
                    (f"{subj} evidence", QueryType.PRIMARY_SOURCE,
                     "Authoritative descriptions of the entities' relationship."),
                    (f"{' '.join(claim.entities[:3]) if claim.entities else subj} roles reversed", QueryType.CONTRADICTION,
                     "Test the reversed-relationship hypothesis."),
                ]
            elif category == HypothesisCategory.TEMPORAL:
                cands += [
                    (f"{subj} {period} history timeline", QueryType.PRIMARY_SOURCE,
                     "Timelines pin facts to periods."),
                ]
            elif category == HypothesisCategory.SOURCE:
                cands += [
                    (f"{subj} debunked OR disproven OR myth", QueryType.CONTRADICTION,
                     "Actively search for refutations."),
                    (f"{subj} scientific consensus OR official record", QueryType.PRIMARY_SOURCE,
                     "The authoritative record settles factual claims."),
                    (f"{subj} criticism OR disputed", QueryType.INDEPENDENT_REPORTING,
                     "Independent critiques reveal weak spots."),
                ]
            elif category == HypothesisCategory.DEFINITIONAL:
                cands += [
                    (f"{subj} definition precise meaning", QueryType.ALTERNATIVE_INTERPRETATION,
                     "Definitional precision tests the claim as stated."),
                ]
            else:
                cands += [
                    (f"{subj} evidence OR record", QueryType.PRIMARY_SOURCE,
                     "Primary records for the asserted fact."),
                    (f"{subj} false OR wrong OR corrected", QueryType.CONTRADICTION,
                     "Direct search for refutation."),
                ]

        # universal adversarial add-ons (low slots, applied once per hypothesis)
        cands.append(
            (f"{subject} independent verification".strip(), QueryType.INDEPENDENT_REPORTING,
             "Independent verification reduces single-source bias.")
        )
        return cands

    def _keyword_fallback(self, claim: Claim) -> str:
        """Content keywords from the normalized text (for claims without numeric slots)."""
        text = claim.normalized_text or claim.original_text
        words = re.findall(r"[A-Za-z][A-Za-z0-9'-]+", text)
        kept: list[str] = []
        for word in words:
            if word.lower() in _STOPWORDS or len(word) < 3:
                continue
            if word not in kept:
                kept.append(word)
            if len(kept) >= 7:
                break
        return " ".join(kept) or text[:60]

    # ------------------------------------------------------------------
    # Optional LLM augmentation
    # ------------------------------------------------------------------

    def _generate_with_llm(
        self, claim: Claim, hypothesis: FalsificationHypothesis
    ) -> list[tuple[str, QueryType, str]]:
        from app.falsify.llm.base import generate_json

        prompt = prompts.build(
            claim.original_text,
            hypothesis.hypothesis,
            hypothesis.category.value,
            hypothesis.falsification_target,
            self._config.max_queries_per_hypothesis,
        )
        try:
            data = generate_json(
                self._llm,  # type: ignore[arg-type]
                prompt,
                system=prompts.system_prompt(prompts.QUERIES_SYSTEM_ROLE),
                max_retries=self._config.llm_max_retries,
                stage="queries",
            )
            items = data.get("queries") if isinstance(data, dict) else data
            if not isinstance(items, list):
                raise LLMError("queries payload is not a list")
        except Exception as exc:
            log_event("llm_queries_skipped", reason=str(exc)[:160], level=30)
            return []

        out: list[tuple[str, QueryType, str]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            query = str(item.get("query", "")).strip()
            if not query:
                continue
            try:
                qtype = QueryType(str(item.get("query_type", "general")).lower())
            except ValueError:
                qtype = QueryType.GENERAL
            out.append((query, qtype, str(item.get("rationale", ""))[:300]))
        return out
