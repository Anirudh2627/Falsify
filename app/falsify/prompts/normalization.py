"""Claim normalization prompt."""

from app.falsify.prompts import system_prompt  # noqa: F401

NORMALIZATION_SYSTEM_ROLE = "claim normalization"

NORMALIZATION_PROMPT = """Normalize the following claim into a structured representation.

CLAIM:
\"\"\"{claim}\"\"\"

Extract:
- entities: named organizations, people, products, places (canonical names)
- predicates: the key relationships/assertions verbs (e.g. "increased", "caused", "orbits")
- temporal_constraints: absolute or relative time references exactly as implied (e.g. "2025", "Q3 2024", "last year")
- geographic_constraints: locations the claim is scoped to
- quantitative_constraints: every numeric assertion with fields:
    metric, raw_value, value (number), unit ("percent"|"USD"|...),
    direction ("increased"|"decreased"|null), comparator ("exactly"|"at least"|"approximately"|null),
    comparison_baseline (e.g. "2024")
- claim_kind: one of quantitative_change | quantitative_state | comparative | causal | factual | future | attribution | unknown
- negated: true if the claim asserts a negative
- is_future_claim: true if it asserts something that has not happened yet
- assertions: split the claim into atomic assertions if it contains more than one
- normalized_text: one concise, unambiguous sentence restating the claim

Do NOT judge whether the claim is true. Do NOT add information not present in the claim.

Return JSON:
{{
  "entities": [...],
  "predicates": [...],
  "temporal_constraints": [...],
  "geographic_constraints": [...],
  "quantitative_constraints": [{{...}}],
  "claim_kind": "...",
  "negated": false,
  "is_future_claim": false,
  "assertions": [...],
  "normalized_text": "..."
}}"""


def build(claim_text: str) -> str:
    return NORMALIZATION_PROMPT.format(claim=claim_text)
