"""Reasoning synthesis prompt (final human-readable 'why')."""

from app.falsify.prompts import system_prompt  # noqa: F401

SYNTHESIS_SYSTEM_ROLE = "verification reasoning synthesis"

SYNTHESIS_PROMPT = """Write the final reasoning summary for an adversarial claim verification.

CLAIM:
\"\"\"{claim}\"\"\"

VERDICT: {verdict}
CONFIDENCE: {confidence:.2f}

FALSIFICATION HYPOTHESES TESTED:
{hypotheses}

EVIDENCE SUMMARY:
{evidence}

CONTRADICTIONS FOUND:
{contradictions}

Write 3-6 sentences explaining, for a skeptical reader:
1. What falsification attempts were made.
2. What evidence was found (cite sources by publisher/title only -- never invent URLs).
3. Why the evidence leads to this specific verdict rather than another.
4. What residual uncertainty remains.

Rules:
- Do not overstate certainty beyond the confidence score.
- Do not introduce facts not present in the evidence summary.
- Never invent citations or URLs.

Return JSON:
{{ "reasoning": "..." }}"""


def build(claim_text: str, verdict: str, confidence: float, hypotheses: str, evidence: str, contradictions: str) -> str:
    return SYNTHESIS_PROMPT.format(
        claim=claim_text,
        verdict=verdict,
        confidence=confidence,
        hypotheses=hypotheses,
        evidence=evidence,
        contradictions=contradictions,
    )
