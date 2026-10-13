"""Adversarial query generation prompt."""

from app.falsify.prompts import system_prompt  # noqa: F401

QUERIES_SYSTEM_ROLE = "adversarial search query generation"

QUERIES_PROMPT = """We are trying to FALSIFY a claim, not confirm it. Design web search queries
that would surface evidence AGAINST the claim.

CLAIM:
\"\"\"{claim}\"\"\"

FALSIFICATION HYPOTHESIS UNDER TEST:
\"\"\"{hypothesis}\"\"\"
(category: {category}; target: {target})

Generate {max_queries} search queries that:
- target primary sources (filings, official reports, datasets, regulatory documents)
- search for contradictory numbers or directions, not the claimed number alone
- probe alternative interpretations/definitions of the claim's key terms
- look for newer corrections, restatements or retractions
- seek independent reporting rather than copies of the original assertion

Rules:
- Queries must be plain search strings (no operators that only one engine supports).
- Never phrase a query so it presumes the claim is true.
- Do not generate near-duplicate queries.

Return JSON:
{{
  "queries": [
    {{
      "query": "...",
      "query_type": "primary_source|contradiction|alternative_interpretation|recency|independent_reporting|general",
      "rationale": "what falsifying evidence this query is designed to surface"
    }}
  ]
}}"""


def build(claim_text: str, hypothesis: str, category: str, target: str, max_queries: int) -> str:
    return QUERIES_PROMPT.format(
        claim=claim_text,
        hypothesis=hypothesis,
        category=category,
        target=target,
        max_queries=max_queries,
    )
