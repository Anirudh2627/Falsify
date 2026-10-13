"""Falsification hypothesis generation.

This is the adversarial core of Falsify: for every claim, enumerate the
concrete ways in which it could be FALSE.  Hypotheses are generated
deterministically from the normalized claim structure (category templates
selected by claim kind), optionally augmented by an LLM.  The engine never
simply searches for the original claim.
"""

from __future__ import annotations

from app.falsify.config import EngineConfig
from app.falsify.exceptions import LLMError
from app.falsify.llm.base import LLMProvider
from app.falsify.llm.provider import NullLLM
from app.falsify.logging_utils import log_event
from app.falsify.models import Claim, ClaimKind, FalsificationHypothesis, HypothesisCategory
from app.falsify.prompts import hypotheses as prompts


class FalsificationEngine:
    """Generates ranked falsification hypotheses for a normalized claim."""

    def __init__(self, config: EngineConfig | None = None, llm: LLMProvider | None = None) -> None:
        self._config = config or EngineConfig()
        self._llm = llm

    def generate_hypotheses(self, claim: Claim) -> list[FalsificationHypothesis]:
        hypotheses = self._generate_deterministic(claim)

        if self._llm is not None and not isinstance(self._llm, NullLLM) and self._config.use_llm_for_hypotheses:
            hypotheses = self._augment_with_llm(claim, hypotheses)

        # rank by priority, cap the list
        hypotheses.sort(key=lambda h: h.priority, reverse=True)
        capped = hypotheses[: self._config.max_hypotheses]

        log_event(
            "hypotheses_generated",
            claim_id=claim.claim_id,
            count=len(capped),
            categories=sorted({h.category.value for h in capped}),
        )
        return capped

    # ------------------------------------------------------------------
    # Deterministic template generation
    # ------------------------------------------------------------------

    def _generate_deterministic(self, claim: Claim) -> list[FalsificationHypothesis]:
        generators = {
            ClaimKind.QUANTITATIVE_CHANGE: self._quantitative_change_hypotheses,
            ClaimKind.QUANTITATIVE_STATE: self._quantitative_state_hypotheses,
            ClaimKind.COMPARATIVE: self._comparative_hypotheses,
            ClaimKind.CAUSAL: self._causal_hypotheses,
            ClaimKind.FACTUAL: self._factual_hypotheses,
            ClaimKind.FUTURE: self._future_hypotheses,
            ClaimKind.ATTRIBUTION: self._attribution_hypotheses,
            ClaimKind.UNKNOWN: self._generic_hypotheses,
        }
        base = generators.get(claim.claim_kind, self._generic_hypotheses)(claim)

        # universal hypotheses that apply to almost any claim
        base.extend(self._universal_hypotheses(claim))

        # dedupe on (category, falsification_target)
        seen: set[tuple[str, str]] = set()
        unique: list[FalsificationHypothesis] = []
        for hyp in base:
            key = (hyp.category.value, hyp.falsification_target.lower())
            if key not in seen:
                seen.add(key)
                unique.append(hyp)
        return unique

    def _mk(
        self,
        claim: Claim,
        category: HypothesisCategory,
        hypothesis: str,
        rationale: str,
        target: str,
        priority: float,
    ) -> FalsificationHypothesis:
        return FalsificationHypothesis(
            claim_id=claim.claim_id,
            category=category,
            hypothesis=hypothesis,
            rationale=rationale,
            falsification_target=target,
            priority=priority,
            origin="deterministic",
        )

    def _slots(self, claim: Claim) -> dict[str, str]:
        q = claim.primary_quantity
        base_forms = {"increased": "increase", "decreased": "decrease"}
        direction = (q.direction if q and q.direction else None) or "changed"
        return {
            "entity": claim.primary_entity or "the subject",
            "metric": (q.metric if q and q.metric else None) or "the reported figure",
            "value": (q.raw_value if q else None) or "the stated value",
            "period": claim.temporal_constraints[0] if claim.temporal_constraints else "the stated period",
            "baseline": (q.comparison_baseline if q and q.comparison_baseline else None) or "the comparison baseline",
            "direction": direction,
            "direction_base": base_forms.get(direction, direction),
            "opposite": "decreased" if (q and q.direction == "increased") else "increased",
            "claim_text": claim.normalized_text or claim.original_text,
        }

    # -- per-kind template sets ------------------------------------------------

    def _quantitative_change_hypotheses(self, claim: Claim) -> list[FalsificationHypothesis]:
        s = self._slots(claim)
        out = [
            self._mk(
                claim,
                HypothesisCategory.NUMERICAL,
                f"{s['entity']}'s {s['metric']} actually {s['opposite']} (or did not {s['direction_base']}) in {s['period']}.",
                "The claimed direction of change may be wrong; authoritative figures would settle this decisively.",
                f"direction of change in {s['metric']}",
                0.95,
            ),
            self._mk(
                claim,
                HypothesisCategory.NUMERICAL,
                f"{s['entity']}'s {s['metric']} changed by a materially different amount than {s['value']} in {s['period']}.",
                "The magnitude may be overstated, understated or simply different from the official figure.",
                f"claimed magnitude {s['value']}",
                0.9,
            ),
            self._mk(
                claim,
                HypothesisCategory.TEMPORAL,
                f"The {s['value']} figure refers to a different period than {s['period']} (e.g. another year or quarter).",
                "Numbers are frequently quoted from the wrong period; the claim's period may not match the source's.",
                f"time period {s['period']}",
                0.75,
            ),
            self._mk(
                claim,
                HypothesisCategory.DEFINITIONAL,
                f"The source uses a different definition of {s['metric']} (e.g. GAAP vs non-GAAP, gross vs net, segment vs consolidated).",
                "Metric definitions differ across sources; the claim may be true only under one definition.",
                f"definition of {s['metric']}",
                0.7,
            ),
            self._mk(
                claim,
                HypothesisCategory.SCOPE,
                f"The claim confuses quarterly and annual {s['metric']}, or applies only to a segment/region rather than {s['entity']} as a whole.",
                "Scope confusion (quarter vs year, division vs company, region vs global) is a common failure mode.",
                "scope of the reported figure",
                0.62,
            ),
            self._mk(
                claim,
                HypothesisCategory.SOURCE,
                f"The {s['value']} figure is preliminary, outdated, or was later restated/corrected.",
                "Early or preliminary figures are often revised; the claim may rely on a superseded number.",
                "currency and finality of the underlying figure",
                0.66,
            ),
        ]
        if len(claim.entities) > 1:
            out.append(
                self._mk(
                    claim,
                    HypothesisCategory.ENTITY,
                    f"The figure actually belongs to a different entity than {s['entity']} (e.g. {claim.entities[1]}).",
                    "Multi-entity claims risk misassigning numbers between entities.",
                    "entity the figure belongs to",
                    0.6,
                )
            )
        return out

    def _quantitative_state_hypotheses(self, claim: Claim) -> list[FalsificationHypothesis]:
        s = self._slots(claim)
        return [
            self._mk(
                claim,
                HypothesisCategory.NUMERICAL,
                f"{s['entity']}'s {s['metric']} was not {s['value']} in {s['period']}; the actual figure differs materially.",
                "The stated value may simply be wrong relative to authoritative records.",
                f"claimed value {s['value']}",
                0.9,
            ),
            self._mk(
                claim,
                HypothesisCategory.TEMPORAL,
                f"The value {s['value']} corresponds to a different period than {s['period']}.",
                "Static figures are period-bound; the wrong period makes the claim false as stated.",
                f"time period {s['period']}",
                0.75,
            ),
            self._mk(
                claim,
                HypothesisCategory.DEFINITIONAL,
                f"The value uses a different definition or unit for {s['metric']} than authoritative sources.",
                "Definitions and units (nominal vs real, gross vs net, currency) change the truth of the claim.",
                f"definition/unit of {s['metric']}",
                0.7,
            ),
            self._mk(
                claim,
                HypothesisCategory.SOURCE,
                f"The figure {s['value']} is preliminary or was later revised.",
                "Official figures are frequently restated after initial publication.",
                "finality of the figure",
                0.65,
            ),
            self._mk(
                claim,
                HypothesisCategory.SCOPE,
                "The figure applies only to a narrower scope (segment, region, subset) than the claim implies.",
                "Scope overreach turns a locally-true figure into a false general claim.",
                "scope of the figure",
                0.6,
            ),
        ]

    def _comparative_hypotheses(self, claim: Claim) -> list[FalsificationHypothesis]:
        s = self._slots(claim)
        others = ", ".join(claim.entities[1:3]) or "the compared entity"
        return [
            self._mk(
                claim,
                HypothesisCategory.NUMERICAL,
                f"The ranking is reversed: {others} actually exceeds {s['entity']} on the stated measure.",
                "Comparative claims are falsified if the true ordering is the opposite.",
                "direction of the comparison",
                0.9,
            ),
            self._mk(
                claim,
                HypothesisCategory.DEFINITIONAL,
                "The comparison uses a different metric or definition than commonly understood.",
                "Comparisons often silently switch metrics (e.g. revenue vs profit, nominal vs real).",
                "metric used in the comparison",
                0.75,
            ),
            self._mk(
                claim,
                HypothesisCategory.TEMPORAL,
                "The comparison is outdated; more recent data reverses or voids it.",
                "Rankings change over time; stale comparisons misstate the present.",
                "currency of the comparison",
                0.7,
            ),
            self._mk(
                claim,
                HypothesisCategory.SCOPE,
                "The comparison holds only in a narrower scope (region, segment, timeframe) than claimed.",
                "Scope restrictions can invalidate a general comparative claim.",
                "scope of the comparison",
                0.6,
            ),
        ]

    def _causal_hypotheses(self, claim: Claim) -> list[FalsificationHypothesis]:
        s = self._slots(claim)
        return [
            self._mk(
                claim,
                HypothesisCategory.CAUSAL,
                f"The asserted cause-effect link for '{s['claim_text'][:120]}' is actually mere correlation.",
                "Correlation is the most common disguise of causation; confounders may explain both.",
                "causal link",
                0.9,
            ),
            self._mk(
                claim,
                HypothesisCategory.CAUSAL,
                "The causation runs in the reverse direction, or a third factor causes both.",
                "Reverse causation and common causes are standard falsifiers of causal claims.",
                "direction/confounding of causation",
                0.85,
            ),
            self._mk(
                claim,
                HypothesisCategory.SCOPE,
                "The causal relationship holds only under specific conditions that the claim omits.",
                "Unstated boundary conditions turn a general causal claim false.",
                "generality of the causal claim",
                0.7,
            ),
            self._mk(
                claim,
                HypothesisCategory.SOURCE,
                "The evidence base for the causal claim has been disputed, retracted or superseded.",
                "Causal claims often rest on single studies that later fail replication.",
                "reliability of the causal evidence base",
                0.65,
            ),
        ]

    def _factual_hypotheses(self, claim: Claim) -> list[FalsificationHypothesis]:
        s = self._slots(claim)
        text_short = s["claim_text"][:140]
        out = [
            self._mk(
                claim,
                HypothesisCategory.ENTITY,
                f"The factual relationship asserted in '{text_short}' is reversed or involves different entities.",
                "Role/entity reversals are the most direct way a factual claim is false.",
                "asserted relationship between entities",
                0.85,
            ),
            self._mk(
                claim,
                HypothesisCategory.DEFINITIONAL,
                f"A key term in '{text_short}' is being used loosely or differently than its accepted definition.",
                "Definitional drift can make an apparently-true statement false as stated.",
                "definitions of key terms",
                0.6,
            ),
            self._mk(
                claim,
                HypothesisCategory.SOURCE,
                "The claim rests on an outdated, retracted or debunked source.",
                "Once-accepted facts are sometimes superseded; the claim may cite stale consensus.",
                "reliability of the underlying source",
                0.65,
            ),
        ]
        if claim.temporal_constraints:
            out.append(
                self._mk(
                    claim,
                    HypothesisCategory.TEMPORAL,
                    f"The statement was true only in a different period than {claim.temporal_constraints[0]}.",
                    "Time-scoped facts can be false for the asserted period.",
                    f"time period {claim.temporal_constraints[0]}",
                    0.7,
                )
            )
        return out

    def _future_hypotheses(self, claim: Claim) -> list[FalsificationHypothesis]:
        s = self._slots(claim)
        return [
            self._mk(
                claim,
                HypothesisCategory.SOURCE,
                f"The forecast underlying '{s['claim_text'][:120]}' has been revised, retracted or superseded.",
                "Forecasts change; a superseded projection cannot support the claim.",
                "currency of the forecast",
                0.7,
            ),
            self._mk(
                claim,
                HypothesisCategory.DEFINITIONAL,
                "The prediction's terms are unfalsifiable as stated or differ from how outcomes will be measured.",
                "Vague future claims often fail on definition rather than outcome.",
                "measurability of the prediction",
                0.5,
            ),
            self._mk(
                claim,
                HypothesisCategory.NUMERICAL,
                "Credible forecasters project materially different numbers/outcomes than the claim asserts.",
                "Divergence from expert consensus weakens a specific future projection.",
                "projected values",
                0.6,
            ),
        ]

    def _attribution_hypotheses(self, claim: Claim) -> list[FalsificationHypothesis]:
        s = self._slots(claim)
        return [
            self._mk(
                claim,
                HypothesisCategory.ATTRIBUTION,
                f"The statement is misquoted, taken out of context, or attributed to the wrong party in '{s['claim_text'][:120]}'.",
                "Misattribution and context-stripping are the primary failure modes of quotation claims.",
                "attribution of the statement",
                0.9,
            ),
            self._mk(
                claim,
                HypothesisCategory.SOURCE,
                "No primary record of the statement exists; it traces only to secondary retellings.",
                "Untraceable quotes are unreliable evidence for attribution claims.",
                "existence of a primary record",
                0.75,
            ),
            self._mk(
                claim,
                HypothesisCategory.TEMPORAL,
                "The statement was made in a different context or time than implied.",
                "Temporal context changes the meaning of quoted statements.",
                "context of the statement",
                0.6,
            ),
        ]

    def _generic_hypotheses(self, claim: Claim) -> list[FalsificationHypothesis]:
        s = self._slots(claim)
        return [
            self._mk(
                claim,
                HypothesisCategory.ENTITY,
                f"The claim misidentifies the entities or their roles in '{s['claim_text'][:120]}'.",
                "Entity/role errors are a universal failure mode.",
                "entity identification",
                0.8,
            ),
            self._mk(
                claim,
                HypothesisCategory.SOURCE,
                "The claim cannot be traced to any reliable primary source.",
                "Unsourced claims deserve an explicit source-existence test.",
                "source existence",
                0.7,
            ),
            self._mk(
                claim,
                HypothesisCategory.DEFINITIONAL,
                "Key terms in the claim are ambiguous or used non-standardly.",
                "Ambiguity can make a claim false under its most natural reading.",
                "term definitions",
                0.55,
            ),
        ]

    def _universal_hypotheses(self, claim: Claim) -> list[FalsificationHypothesis]:
        """Applies to every claim kind: staleness and negation checks."""
        s = self._slots(claim)
        out = [
            self._mk(
                claim,
                HypothesisCategory.SOURCE,
                f"Newer, authoritative information (published after the claim's basis) contradicts '{s['claim_text'][:100]}'.",
                "Even true claims become false when superseded; recency must always be probed.",
                "recency of the claim's basis",
                0.55,
            ),
        ]
        if claim.negated:
            out.append(
                self._mk(
                    claim,
                    HypothesisCategory.NUMERICAL,
                    "The negation is wrong: the positive form of the claim actually holds.",
                    "Negated claims are falsified by evidence for their positive form.",
                    "the negation itself",
                    0.85,
                )
            )
        return out

    # ------------------------------------------------------------------
    # Optional LLM augmentation
    # ------------------------------------------------------------------

    def _augment_with_llm(
        self, claim: Claim, existing: list[FalsificationHypothesis]
    ) -> list[FalsificationHypothesis]:
        from app.falsify.llm.base import generate_json

        structure = (
            f"kind={claim.claim_kind.value}; entities={claim.entities}; "
            f"temporal={claim.temporal_constraints}; "
            f"quantities={[q.model_dump(exclude_none=True) for q in claim.quantitative_constraints]}"
        )
        prompt = prompts.build(claim.original_text, structure)
        try:
            data = generate_json(
                self._llm,  # type: ignore[arg-type]
                prompt,
                system=prompts.system_prompt(prompts.HYPOTHESES_SYSTEM_ROLE),
                max_retries=self._config.llm_max_retries,
                stage="hypotheses",
            )
            items = data.get("hypotheses") if isinstance(data, dict) else data
            if not isinstance(items, list):
                raise LLMError("hypotheses payload is not a list")
        except Exception as exc:
            log_event("llm_hypotheses_skipped", reason=str(exc)[:160], level=30)
            return existing

        seen_keys = {(h.category.value, h.falsification_target.lower()) for h in existing}
        seen_texts = {h.hypothesis.lower() for h in existing}
        added = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                category = HypothesisCategory(str(item.get("category", "")).lower())
            except ValueError:
                continue
            text = str(item.get("hypothesis", "")).strip()
            target = str(item.get("falsification_target", "")).strip().lower()
            if not text or text.lower() in seen_texts or (category.value, target) in seen_keys:
                continue
            try:
                priority = float(item.get("priority", 0.5))
            except (TypeError, ValueError):
                priority = 0.5
            existing.append(
                FalsificationHypothesis(
                    claim_id=claim.claim_id,
                    category=category,
                    hypothesis=text,
                    rationale=str(item.get("rationale", ""))[:500],
                    falsification_target=target or category.value,
                    priority=max(0.0, min(1.0, priority)),
                    origin="llm",
                )
            )
            seen_keys.add((category.value, target))
            seen_texts.add(text.lower())
            added += 1
            if added >= 4:
                break
        if added:
            log_event("llm_hypotheses_added", count=added)
        return existing
