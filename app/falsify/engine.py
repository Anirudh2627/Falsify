"""FalsifyEngine -- top-level orchestrator of the adversarial verification pipeline.

Pipeline stages (each structured-logged and individually failure-tolerant):

1. Normalize claim            (:class:`ClaimNormalizer`)
2. Generate falsification hypotheses (:class:`FalsificationEngine`)
3. Generate adversarial queries      (:class:`AdversarialQueryGenerator`)
4. Retrieve evidence                 (any :class:`EvidenceRetriever`)
5. Assess evidence                   (:class:`EvidenceAnalyzer`)
6. Detect contradictions             (:class:`ContradictionDetector`)
7. Fuse evidence                     (:class:`EvidenceFusion`)
8. Determine verdict                 (:class:`VerdictEngine`)
9. Compute confidence                (:class:`ConfidenceCalculator`)
10. Synthesize reasoning trace

All collaborators are injected; :func:`build_default_engine` wires production
defaults from environment variables.
"""

from __future__ import annotations

import time

from app.falsify.analysis.contradiction import ContradictionDetector
from app.falsify.analysis.evidence import EvidenceAnalyzer
from app.falsify.analysis.source_quality import SourceQualityScorer
from app.falsify.config import EngineConfig
from app.falsify.exceptions import ClaimValidationError
from app.falsify.fusion.confidence import ConfidenceCalculator
from app.falsify.fusion.evidence_fusion import EvidenceFusion, normalize_url
from app.falsify.fusion.verdict import VerdictEngine
from app.falsify.hypotheses.generator import FalsificationEngine
from app.falsify.llm.base import LLMProvider
from app.falsify.llm.provider import NullLLM, build_llm_from_config
from app.falsify.logging_utils import log_event
from app.falsify.models import (
    Claim,
    Contradiction,
    ContradictionTraceEntry,
    Evidence,
    EvidenceAssessment,
    EvidenceTraceEntry,
    FalsificationHypothesis,
    FusionSummary,
    HypothesisTraceEntry,
    PipelineError,
    QueryTraceEntry,
    ReasoningTrace,
    SearchQuery,
    Severity,
    Verdict,
    VerificationResult,
)
from app.falsify.normalization.normalizer import ClaimNormalizer
from app.falsify.prompts import synthesis as synthesis_prompts
from app.falsify.queries.generator import AdversarialQueryGenerator
from app.falsify.retrieval import build_retriever_from_config
from app.falsify.retrieval.base import EvidenceRetriever

# hypothesis category <-> contradiction type correspondence for trace outcomes
_CATEGORY_TYPE_MAP = {
    "numerical": "numerical",
    "temporal": "temporal",
    "entity": "entity",
    "definitional": "definitional",
    "causal": "causal",
    "scope": "scope",
    "attribution": "attribution",
    "source": None,  # source contradictions surface as any type
}


class FalsifyEngine:
    """Public entry point of the Falsify core intelligence component.

    Usage::

        engine = FalsifyEngine(config=..., llm=..., retriever=...)
        result = engine.verify("Company X grew revenue by 40% in 2025.")
        result.verdict, result.confidence, result.reasoning_trace
    """

    def __init__(
        self,
        config: EngineConfig | None = None,
        llm: LLMProvider | None = None,
        retriever: EvidenceRetriever | None = None,
        *,
        normalizer: ClaimNormalizer | None = None,
        falsification_engine: FalsificationEngine | None = None,
        query_generator: AdversarialQueryGenerator | None = None,
        evidence_analyzer: EvidenceAnalyzer | None = None,
        contradiction_detector: ContradictionDetector | None = None,
        fusion: EvidenceFusion | None = None,
        verdict_engine: VerdictEngine | None = None,
        confidence_calculator: ConfidenceCalculator | None = None,
    ) -> None:
        self.config = config or EngineConfig()
        self._llm = llm if llm is not None else NullLLM()
        if retriever is None:
            retriever = build_retriever_from_config(self.config.retrieval)
        self._retriever = retriever

        self._normalizer = normalizer or ClaimNormalizer(self.config, self._llm)
        self._falsification = falsification_engine or FalsificationEngine(self.config, self._llm)
        self._queries = query_generator or AdversarialQueryGenerator(self.config, self._llm)
        self._analyzer = evidence_analyzer or EvidenceAnalyzer(self.config, self._llm, SourceQualityScorer())
        self._contradictions = contradiction_detector or ContradictionDetector(self.config, self._llm)
        self._fusion = fusion or EvidenceFusion(self.config)
        self._verdict = verdict_engine or VerdictEngine(self.config)
        self._confidence = confidence_calculator or ConfidenceCalculator(self.config)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def verify(self, claim_text: str) -> VerificationResult:
        """Run the full adversarial verification pipeline on a claim.

        Raises:
            ClaimValidationError: the input is empty/too long (caller error).

        Never raises for retrieval or LLM failures -- those are recorded as
        structured :class:`PipelineError` entries and reflected in the verdict
        (typically UNVERIFIABLE) instead.
        """
        timers: dict[str, float] = {}
        errors: list[PipelineError] = []

        # 1) normalize -----------------------------------------------------
        t0 = time.perf_counter()
        claim = self._normalizer.normalize(claim_text)  # may raise ClaimValidationError
        timers["normalization"] = t0

        # 2) hypotheses ----------------------------------------------------
        t = time.perf_counter()
        hypotheses = self._safe(
            "hypotheses", lambda: self._falsification.generate_hypotheses(claim), [], errors
        )
        timers["hypotheses"] = t

        # 3) adversarial queries --------------------------------------------
        t = time.perf_counter()
        queries = self._generate_queries(claim, hypotheses, errors)
        timers["queries"] = t
        log_event("queries_generated", count=len(queries), hypotheses=len(hypotheses))

        # 4) retrieval --------------------------------------------------------
        t = time.perf_counter()
        evidence, retrieval_failures, ids_by_query = self._retrieve(queries, errors)
        timers["retrieval"] = t
        log_event(
            "evidence_retrieved",
            items=len(evidence),
            queries=len(queries),
            failures=retrieval_failures,
            provider=self._retriever.name,
        )

        # 5) assessment ---------------------------------------------------------
        t = time.perf_counter()
        assessments = self._assess(claim, evidence, errors)
        timers["assessment"] = t
        stance_counts = {"supporting": 0, "contradicting": 0, "neutral": 0, "mixed": 0}
        for a in assessments:
            stance_counts[a.stance] += 1
        log_event("evidence_assessed", **stance_counts)

        # 6) contradiction detection -------------------------------------------
        t = time.perf_counter()
        pairs = [
            (ev, next(a for a in assessments if a.evidence_id == ev.evidence_id))
            for ev in evidence
        ]
        contradictions = self._safe(
            "contradictions", lambda: self._contradictions.detect(claim, pairs), [], errors
        )
        timers["contradictions"] = t

        # 7) fusion -----------------------------------------------------------------
        t = time.perf_counter()
        relevant_ids = {a.evidence_id for a in assessments if a.relevance_score >= self.config.relevance_floor}
        relevant_ids_by_query = {qid: ids & relevant_ids for qid, ids in ids_by_query.items()}
        fusion_summary, clusters = self._fusion.fuse(
            claim=claim,
            hypotheses=hypotheses,
            queries=queries,
            evidence=evidence,
            assessments=assessments,
            retrieval_failures=retrieval_failures,
            relevant_ids_by_query=relevant_ids_by_query,
        )
        timers["fusion"] = t

        # 8) verdict -------------------------------------------------------------------
        decision = self._verdict.decide(claim, fusion_summary, contradictions)

        # 9) confidence ------------------------------------------------------------------
        confidence, breakdown, confidence_explanation = self._confidence.compute(
            claim=claim,
            verdict=decision.verdict,
            fusion=fusion_summary,
            clusters=clusters,
            contradictions=contradictions,
            relevance_by_id={a.evidence_id: a.relevance_score for a in assessments},
            quality_by_id={a.evidence_id: a.source_quality_score for a in assessments},
            temporal_by_id={a.evidence_id: a.temporal_validity for a in assessments},
            stance_by_id={a.evidence_id: a.stance for a in assessments},
        )

        # 10) reasoning synthesis + trace ------------------------------------------------
        reasoning = self._synthesize(claim, decision, confidence, hypotheses, assessments, contradictions, errors)
        trace = self._build_trace(
            claim=claim,
            hypotheses=hypotheses,
            queries=queries,
            evidence=evidence,
            assessments=assessments,
            contradictions=contradictions,
            fusion=fusion_summary,
            verdict=decision.verdict,
            rationale=decision.rationale,
            confidence=confidence,
            confidence_explanation=confidence_explanation,
            reasoning=reasoning,
            errors=errors,
            timers=timers,
        )

        result = VerificationResult(
            claim_id=claim.claim_id,
            claim_text=claim.original_text,
            verdict=decision.verdict,
            confidence=confidence,
            confidence_explanation=confidence_explanation,
            confidence_breakdown=breakdown,
            claim=claim,
            hypotheses=hypotheses,
            queries=queries,
            evidence=evidence,
            assessments=assessments,
            contradictions=contradictions,
            fusion=fusion_summary,
            reasoning_trace=trace,
            errors=errors,
            llm_used=not isinstance(self._llm, NullLLM),
            retrieval_provider=self._retriever.name,
        )
        log_event(
            "verification_complete",
            claim_id=claim.claim_id,
            verdict=result.verdict.value,
            confidence=result.confidence,
            evidence=len(evidence),
            errors=len(errors),
        )
        return result

    # ------------------------------------------------------------------
    # Stage implementations
    # ------------------------------------------------------------------

    def _safe(self, stage: str, fn, default, errors: list[PipelineError]):
        try:
            return fn()
        except ClaimValidationError:
            raise
        except Exception as exc:  # pipeline must never crash on a stage failure
            errors.append(
                PipelineError(stage=stage, error_type=type(exc).__name__, message=str(exc)[:400])
            )
            log_event("stage_failed", stage=stage, error=str(exc)[:160], level=40)
            return default

    def _generate_queries(
        self, claim: Claim, hypotheses: list[FalsificationHypothesis], errors: list[PipelineError]
    ) -> list[SearchQuery]:
        queries: list[SearchQuery] = []
        seen: set[str] = set()
        for hypothesis in hypotheses:  # already priority-sorted
            if len(queries) >= self.config.max_total_queries:
                break
            batch = self._safe(
                "query_generation",
                lambda h=hypothesis: self._queries.generate(claim, h, exclude=seen),
                [],
                errors,
            )
            for query in batch:
                if len(queries) >= self.config.max_total_queries:
                    break
                seen.add(query.query.lower())
                queries.append(query)
        return queries

    def _retrieve(
        self, queries: list[SearchQuery], errors: list[PipelineError]
    ) -> tuple[list[Evidence], int, dict[str, set[str]]]:
        evidence: list[Evidence] = []
        seen_urls: dict[str, str] = {}  # normalized url -> canonical evidence_id
        ids_by_query: dict[str, set[str]] = {}
        failures = 0
        for query in queries:
            if len(evidence) >= self.config.max_total_evidence:
                break
            try:
                items = self._retriever.search(query.query, max_results=self.config.max_evidence_per_query)
            except Exception as exc:
                failures += 1
                errors.append(
                    PipelineError(
                        stage="retrieval",
                        error_type=type(exc).__name__,
                        message=str(exc)[:300],
                        query=query.query[:200],
                    )
                )
                log_event("retrieval_failed", query_id=query.query_id, error=str(exc)[:140], level=30)
                continue
            for item in items:
                key = normalize_url(item.source_url)
                canonical_id = seen_urls.get(key)
                if canonical_id is None:
                    item.query_id = query.query_id
                    seen_urls[key] = item.evidence_id
                    evidence.append(item)
                    canonical_id = item.evidence_id
                    if len(evidence) >= self.config.max_total_evidence:
                        break
                # record which (canonical) evidence this query surfaced, even if
                # the same URL was already kept under an earlier query
                ids_by_query.setdefault(query.query_id, set()).add(canonical_id)
        return evidence, failures, ids_by_query

    def _assess(
        self, claim: Claim, evidence: list[Evidence], errors: list[PipelineError]
    ) -> list[EvidenceAssessment]:
        assessments: list[EvidenceAssessment] = []
        for item in evidence:
            assessment = self._safe(
                "evidence_assessment",
                lambda e=item: self._analyzer.assess(claim, e),
                None,
                errors,
            )
            if assessment is None:  # stage failure: neutral placeholder, never fabricated
                assessment = EvidenceAssessment(
                    evidence_id=item.evidence_id,
                    reasoning="Assessment failed; treated as neutral (no fabricated stance).",
                )
            assessments.append(assessment)
        return assessments

    def _synthesize(
        self,
        claim: Claim,
        decision,
        confidence: float,
        hypotheses: list[FalsificationHypothesis],
        assessments: list[EvidenceAssessment],
        contradictions: list[Contradiction],
        errors: list[PipelineError],
    ) -> str:
        fallback = self._template_reasoning(claim, decision, confidence, assessments, contradictions, errors)
        if isinstance(self._llm, NullLLM) or not self.config.use_llm_for_synthesis:
            return fallback
        try:
            from app.falsify.llm.base import generate_json

            hyp_text = "\n".join(f"- [{h.category.value}] {h.hypothesis}" for h in hypotheses) or "- none"
            ev_text = "\n".join(
                f"- stance={a.stance} quality={a.source_quality_score:.2f} relevance={a.relevance_score:.2f}: {a.reasoning[:180]}"
                for a in assessments[:12]
            ) or "- no evidence"
            ctr_text = "\n".join(
                f"- [{c.contradiction_type.value}/{c.severity.value}] {c.explanation[:180]}" for c in contradictions
            ) or "- none"
            prompt = synthesis_prompts.build(
                claim.original_text, decision.verdict.value, confidence, hyp_text, ev_text, ctr_text
            )
            data = generate_json(
                self._llm,
                prompt,
                system=synthesis_prompts.system_prompt(synthesis_prompts.SYNTHESIS_SYSTEM_ROLE),
                max_retries=self.config.llm_max_retries,
                stage="synthesis",
            )
            reasoning = data.get("reasoning") if isinstance(data, dict) else None
            if isinstance(reasoning, str) and reasoning.strip():
                return f"{reasoning.strip()}\n\n[Deterministic rationale] {decision.rationale}"
        except Exception as exc:
            log_event("llm_synthesis_skipped", reason=str(exc)[:140], level=30)
        return fallback

    @staticmethod
    def _template_reasoning(
        claim: Claim,
        decision,
        confidence: float,
        assessments: list[EvidenceAssessment],
        contradictions: list[Contradiction],
        errors: list[PipelineError],
    ) -> str:
        supporting = sum(1 for a in assessments if a.stance == "supporting")
        contradicting = sum(1 for a in assessments if a.stance == "contradicting")
        lines = [
            f"Claim: {claim.original_text}",
            f"Verdict: {decision.verdict.value} (confidence {confidence:.2f}). {decision.rationale}",
            f"Evidence examined: {len(assessments)} source(s) -- {supporting} supporting, {contradicting} contradicting.",
        ]
        if contradictions:
            lines.append(
                "Contradictions: "
                + "; ".join(f"{c.contradiction_type.value} ({c.severity.value}): {c.explanation[:160]}" for c in contradictions)
            )
        if errors:
            lines.append(f"Pipeline recorded {len(errors)} non-fatal error(s): " + "; ".join(e.message[:100] for e in errors[:3]))
        return "\n".join(lines)

    def _build_trace(
        self,
        *,
        claim: Claim,
        hypotheses: list[FalsificationHypothesis],
        queries: list[SearchQuery],
        evidence: list[Evidence],
        assessments: list[EvidenceAssessment],
        contradictions: list[Contradiction],
        fusion: FusionSummary,
        verdict: Verdict,
        rationale: str,
        confidence: float,
        confidence_explanation: str,
        reasoning: str,
        errors: list[PipelineError],
        timers: dict[str, float],
    ) -> ReasoningTrace:
        assessment_by_id = {a.evidence_id: a for a in assessments}
        evidence_by_query: dict[str, list[Evidence]] = {}
        for ev in evidence:
            evidence_by_query.setdefault(ev.query_id or "", []).append(ev)

        hyp_by_id = {h.hypothesis_id: h for h in hypotheses}
        contradiction_types_by_severity: dict[str, Severity] = {}
        for c in contradictions:
            contradiction_types_by_severity[c.contradiction_type.value] = c.severity

        hypothesis_entries: list[HypothesisTraceEntry] = []
        for h in hypotheses:
            h_queries = [q for q in queries if q.hypothesis_id == h.hypothesis_id]
            h_evidence = [ev for q in h_queries for ev in evidence_by_query.get(q.query_id, [])]
            relevant = [ev for ev in h_evidence if assessment_by_id.get(ev.evidence_id) and assessment_by_id[ev.evidence_id].relevance_score >= self.config.relevance_floor]
            mapped_type = _CATEGORY_TYPE_MAP.get(h.category.value)
            severity = contradiction_types_by_severity.get(mapped_type) if mapped_type else None
            if severity in (Severity.HIGH, Severity.CRITICAL):
                outcome = "falsified"
            elif severity in (Severity.LOW, Severity.MEDIUM):
                outcome = "challenged"
            elif relevant:
                outcome = "survived"
            elif h_queries:
                outcome = "no_evidence"
            else:
                outcome = "not_tested"
            hypothesis_entries.append(
                HypothesisTraceEntry(
                    hypothesis_id=h.hypothesis_id,
                    hypothesis=h.hypothesis,
                    category=h.category,
                    priority=h.priority,
                    tested=bool(h_queries),
                    queries_run=len(h_queries),
                    evidence_found=len(h_evidence),
                    outcome=outcome,
                )
            )

        error_queries = {(e.query or "") for e in errors if e.stage == "retrieval"}
        query_entries = [
            QueryTraceEntry(
                query_id=q.query_id,
                query=q.query,
                hypothesis=hyp_by_id[q.hypothesis_id].hypothesis if q.hypothesis_id in hyp_by_id else "",
                purpose=q.rationale,
                query_type=q.query_type,
                results_found=len(evidence_by_query.get(q.query_id, [])),
                retrieval_error=("retrieval failed" if q.query in error_queries else None),
            )
            for q in queries
        ]

        evidence_entries = []
        for ev in evidence:
            a = assessment_by_id.get(ev.evidence_id)
            if a is None:
                continue
            passage = (ev.relevant_passages[0] if ev.relevant_passages else ev.retrieved_text)[:300]
            evidence_entries.append(
                EvidenceTraceEntry(
                    evidence_id=ev.evidence_id,
                    url=ev.source_url,
                    title=ev.title,
                    publisher=ev.publisher,
                    source_tier=a.source_tier,
                    stance=a.stance,
                    relevance_score=a.relevance_score,
                    source_quality_score=a.source_quality_score,
                    temporal_validity=a.temporal_validity,
                    is_direct=a.is_direct,
                    reasoning=a.reasoning,
                    key_passage=passage,
                )
            )

        url_by_evidence = {ev.evidence_id: ev.source_url for ev in evidence}
        contradiction_entries = [
            ContradictionTraceEntry(
                contradiction_id=c.contradiction_id,
                type=c.contradiction_type,
                severity=c.severity,
                explanation=c.explanation,
                evidence_urls=[url_by_evidence[eid] for eid in c.evidence_ids if eid in url_by_evidence],
            )
            for c in contradictions
        ]

        timings = {}
        marks = sorted(timers.items(), key=lambda kv: kv[1])
        for idx, (stage, start) in enumerate(marks):
            end = marks[idx + 1][1] if idx + 1 < len(marks) else time.perf_counter()
            timings[stage] = int((end - start) * 1000)

        return ReasoningTrace(
            claim=claim.original_text,
            normalized_claim=claim.normalized_text,
            claim_kind=claim.claim_kind,
            hypotheses=hypothesis_entries,
            queries=query_entries,
            evidence_summary={
                "supporting": fusion.supporting_evidence,
                "contradicting": fusion.contradicting_evidence,
                "neutral": fusion.neutral_evidence,
                "total": fusion.total_evidence,
            },
            evidence=evidence_entries,
            contradictions=contradiction_entries,
            fusion=fusion,
            verdict=verdict,
            confidence=confidence,
            confidence_explanation=confidence_explanation,
            reasoning=reasoning,
            errors=[f"{e.stage}: {e.message}" for e in errors],
            stage_timings_ms=timings,
        )


def build_default_engine(**config_overrides) -> FalsifyEngine:
    """Production factory: wires providers from environment variables.

    * ``TAVILY_API_KEY`` -- retrieval (missing -> empty retriever -> UNVERIFIABLE)
    * ``LLM_API_KEY`` / ``NEBIUS_API_KEY``, ``LLM_BASE_URL``, ``LLM_MODEL`` -- LLM
      (missing -> deterministic-only pipeline)
    """
    config = EngineConfig.from_env(**config_overrides)
    llm = build_llm_from_config(config.llm)
    retriever = build_retriever_from_config(config.retrieval)
    return FalsifyEngine(config=config, llm=llm, retriever=retriever)
