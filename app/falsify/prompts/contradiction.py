"""Contradiction analysis prompt."""

from app.falsify.prompts import system_prompt  # noqa: F401

CONTRADICTION_SYSTEM_ROLE = "contradiction analysis"

CONTRADICTION_PROMPT = """Decide whether a source genuinely CONTRADICTS a claim.

CLAIM:
\"\"\"{claim}\"\"\"

CLAIM ELEMENTS: {elements}

SOURCE PASSAGES:
\"\"\"{passages}\"\"\"

A contradiction requires that the source, if accurate, makes the claim (as stated) false.
Classify the contradiction, if any:
- numerical: actual value differs materially from the claimed value (mind implied precision:
  "increased 20%" vs "increased 19.8%" is at most a low-severity discrepancy;
  "increased 30%" vs "increased 21%" is high severity; "increased" vs "decreased" is critical)
- temporal: the fact is attached to a different period than claimed
- entity: the fact belongs to a different entity than claimed
- definitional: the metric/term is defined differently, changing the truth of the claim
- causal: the asserted causal link is denied or reversed
- scope: true only in a narrower scope than the claim states
- attribution: the claim misattributes a statement or source

Severity: low | medium | high | critical.

Rules:
- Irrelevant or merely tangential sources are NOT contradictions.
- Corroboration of the claim is NOT a contradiction.
- Do not invent contradictions the passages do not support.

Return JSON:
{{
  "is_contradiction": false,
  "contradiction_type": null,
  "severity": null,
  "explanation": "why the passages do or do not falsify the claim as stated"
}}"""


def build(claim_text: str, elements: str, passages: str) -> str:
    return CONTRADICTION_PROMPT.format(claim=claim_text, elements=elements, passages=passages[:5000])
