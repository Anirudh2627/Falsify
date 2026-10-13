"""Shared numeric comparison logic.

Used by both the evidence analyzer and the contradiction detector so the
"does this number agree with the claim?" decision is made in exactly one
place with one consistent tolerance policy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.falsify.models import QuantitativeConstraint

_INCREASE_WORDS = (
    "increased", "increase", "grew", "growth", "grown", "rose", "rise", "risen", "climbed",
    "jumped", "surged", "soared", "expanded", "doubled", "tripled", "gained", "up",
    "higher", "raised", "boosted", "beat", "exceeded",
)
_DECREASE_WORDS = (
    "decreased", "decrease", "declined", "decline", "fell", "fall", "fallen", "dropped",
    "plunged", "slumped", "shrank", "shrunk", "contracted", "reduced", "lowered", "lost",
    "down", "sank", "halved", "missed", "lower",
)

_PERCENT_RE = re.compile(r"([-+]?\d[\d,]*(?:\.\d+)?)\s*(%|percent(?:age points)?|pp)(?![a-z])", re.IGNORECASE)
_NUM_DIR_RE = re.compile(
    rf"({'|'.join(sorted(_INCREASE_WORDS + _DECREASE_WORDS, key=len, reverse=True))})\D{{0,40}}?([-+]?\d[\d,]*(?:\.\d+)?)\s*(%|percent)?(?![a-z])",
    re.IGNORECASE,
)
_NEGATION_RE = re.compile(r"\b(not|never|no longer|didn't|did not|doesn't|does not|wasn't|was not)\b", re.IGNORECASE)


@dataclass
class NumericObservation:
    """A number observed in evidence text, with its direction if stated."""

    value: float
    raw: str
    unit: str | None  # 'percent' or None
    direction: str | None  # 'increased' | 'decreased' | None
    negated: bool = False

    @property
    def effective_direction(self) -> str | None:
        if self.direction is None:
            return None
        if self.negated:
            return "decreased" if self.direction == "increased" else "increased"
        return self.direction


@dataclass
class NumericComparison:
    """Result of comparing an observed value against a claimed quantity."""

    kind: str  # 'match' | 'magnitude_mismatch' | 'direction_mismatch' | 'unrelated' | 'no_observation'
    claim_value: float | None = None
    observed_value: float | None = None
    relative_gap: float = 0.0  # |claim - observed| / max(|claim|, eps)
    tolerance_used: float = 0.0
    direction_agrees: bool | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def supports(self) -> bool:
        return self.kind == "match"

    @property
    def contradicts(self) -> bool:
        return self.kind in ("magnitude_mismatch", "direction_mismatch")


def extract_numeric_observations(text: str, metric_hint: str | None = None) -> list[NumericObservation]:
    """Extract directional numeric statements from evidence text.

    Prefers numbers appearing near ``metric_hint`` (e.g. 'revenue'), falling
    back to any percent/number+direction statement.
    """
    lowered = text.lower()
    observations: list[NumericObservation] = []

    def _direction_of(word: str) -> str | None:
        w = word.lower()
        if w in _INCREASE_WORDS:
            return "increased"
        if w in _DECREASE_WORDS:
            return "decreased"
        return None

    # 1) direction-word ... number patterns (e.g. "revenue grew 21%")
    for match in _NUM_DIR_RE.finditer(lowered):
        word, raw, pct = match.group(1), match.group(2), match.group(3)
        value = _parse(raw)
        if value is None:
            continue
        window_before = lowered[max(0, match.start() - 40) : match.start()]
        negated = bool(_NEGATION_RE.search(window_before))
        observations.append(
            NumericObservation(
                value=abs(value),
                raw=match.group(0).strip(),
                unit="percent" if pct else None,
                direction=_direction_of(word),
                negated=negated,
            )
        )

    # 2) bare percentages ("revenue growth of 21%", "21% increase")
    for match in _PERCENT_RE.finditer(lowered):
        value = _parse(match.group(1))
        if value is None:
            continue
        window = lowered[max(0, match.start() - 60) : match.end() + 20]
        direction: str | None = None
        for word in _INCREASE_WORDS:
            if re.search(rf"\b{word}\b", window):
                direction = "increased"
                break
        if direction is None:
            for word in _DECREASE_WORDS:
                if re.search(rf"\b{word}\b", window):
                    direction = "decreased"
                    break
        negated = bool(_NEGATION_RE.search(lowered[max(0, match.start() - 60) : match.start()]))
        observations.append(
            NumericObservation(
                value=abs(value),
                raw=match.group(0).strip(),
                unit="percent",
                direction=direction,
                negated=negated,
            )
        )

    # Prefer observations near the metric hint
    if metric_hint:
        hint = metric_hint.lower()
        near: list[NumericObservation] = []
        for obs in observations:
            pos = lowered.find(obs.raw.lower())
            if pos >= 0:
                window = lowered[max(0, pos - 120) : pos + 120]
                if hint in window:
                    near.append(obs)
        if near:
            observations = near

    # de-duplicate by (value, direction)
    unique: list[NumericObservation] = []
    seen: set[tuple[float, str | None]] = set()
    for obs in observations:
        key = (round(obs.value, 6), obs.effective_direction)
        if key not in seen:
            seen.add(key)
            unique.append(obs)
    return unique


def compare_quantity(
    claim_q: QuantitativeConstraint,
    observation: NumericObservation,
    *,
    rel_tol: float = 0.02,
) -> NumericComparison:
    """Compare one observed number against the claimed quantity.

    Tolerance policy (per the product spec):
    * direction mismatch ('increased' vs 'decreased') is always a contradiction;
    * values agree within ``max(implied rounding precision, rel_tol * value)``
      -> match (e.g. 19.8% vs "20%" is rounding-compatible);
    * 'exactly'/'precisely' comparators remove rounding slack;
    * otherwise it is a magnitude mismatch, sized by relative gap.
    """
    claim_value = claim_q.value
    if claim_value is None:
        return NumericComparison(kind="no_observation")

    # unit mismatch (percent vs absolute) -> cannot compare numerically
    if claim_q.is_percentage != (observation.unit == "percent"):
        return NumericComparison(kind="unrelated", claim_value=claim_value, observed_value=observation.value)

    direction_agrees: bool | None = None
    if claim_q.direction and observation.effective_direction:
        direction_agrees = claim_q.direction == observation.effective_direction
        if not direction_agrees:
            return NumericComparison(
                kind="direction_mismatch",
                claim_value=claim_value,
                observed_value=observation.value,
                direction_agrees=False,
                notes=[
                    f"claim says '{claim_q.direction}', evidence says '{observation.effective_direction}'"
                ],
            )

    exact = (claim_q.comparator or "").lower() in {"exactly", "precisely"}
    precision = 0.0 if exact else (claim_q.implied_precision or 0.0)
    tolerance = max(precision, rel_tol * abs(claim_value))
    gap = abs(claim_value - observation.value)
    relative_gap = gap / max(abs(claim_value), 1e-9)

    comparison = NumericComparison(
        kind="match" if gap <= tolerance else "magnitude_mismatch",
        claim_value=claim_value,
        observed_value=observation.value,
        relative_gap=relative_gap,
        tolerance_used=tolerance,
        direction_agrees=direction_agrees,
    )
    if comparison.kind == "match":
        comparison.notes.append(
            f"observed {observation.value} agrees with claimed {claim_value} within tolerance {tolerance:.3g}"
        )
    else:
        comparison.notes.append(
            f"observed {observation.value} differs from claimed {claim_value} "
            f"(gap {gap:.3g} > tolerance {tolerance:.3g}, relative {relative_gap:.1%})"
        )
    return comparison


def best_comparison(
    claim_q: QuantitativeConstraint,
    observations: list[NumericObservation],
    *,
    rel_tol: float = 0.02,
) -> NumericComparison | None:
    """Pick the most decisive comparison among several observations.

    Priority: direction mismatch > match > magnitude mismatch > unrelated.
    Among magnitude mismatches, the one closest to the claim (smallest gap
    still contradicting) is most informative about severity; among matches,
    any match suffices.
    """
    if not observations or claim_q.value is None:
        return None
    comparisons = [compare_quantity(claim_q, obs, rel_tol=rel_tol) for obs in observations]
    comparisons = [c for c in comparisons if c.kind != "no_observation"]
    if not comparisons:
        return None
    rank = {"direction_mismatch": 0, "match": 1, "magnitude_mismatch": 2, "unrelated": 3}
    comparisons.sort(key=lambda c: (rank.get(c.kind, 4), c.relative_gap))
    return comparisons[0]


def _parse(raw: str) -> float | None:
    try:
        return float(raw.replace(",", ""))
    except ValueError:
        return None
