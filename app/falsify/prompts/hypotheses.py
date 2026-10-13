"""Falsification hypothesis generation prompt."""

from app.falsify.prompts import system_prompt  # noqa: F401

HYPOTHESES_SYSTEM_ROLE = "falsification hypothesis generation"

HYPOTHESES_PROMPT = """A claim has been made. Your job is NOT to verify it -- it is to enumerate
the strongest concrete ways in which it could be FALSE.

CLAIM:
\"\"\"{claim}\"\"\"

NORMALIZED STRUCTURE (deterministically extracted, may be incomplete):
{structure}

Generate falsification hypotheses across these categories where applicable:
- numerical: the actual number differs from the claimed one (direction or magnitude)
- temporal: the claim attaches the fact to the wrong time period
- entity: the fact belongs to a different entity, or the entity is misidentified
- causal: an asserted cause-effect link is correlation, reversed, or confounded
- definitional: the key term/metric is defined differently by authoritative sources
- attribution: the statement is attributed to the wrong source or misquoted
- source: the underlying figure is preliminary, restated, outdated or retracted
- scope: the claim holds only in a narrower scope than stated (segment, region, subset)

Rules:
- Each hypothesis must be independently testable via evidence retrieval.
- Prioritize hypotheses that authoritative sources could decisively settle.
- Only include categories that plausibly apply to THIS claim's structure.
- Do not include generic filler hypotheses.

Return JSON:
{{
  "hypotheses": [
    {{
      "category": "...",
      "hypothesis": "one sentence stating how the claim could be false",
      "rationale": "why this is a plausible failure mode",
      "falsification_target": "the specific element of the claim being attacked",
      "priority": 0.0-1.0
    }}
  ]
}}"""


def build(claim_text: str, structure_summary: str) -> str:
    return HYPOTHESES_PROMPT.format(claim=claim_text, structure=structure_summary)
