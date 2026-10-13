"""Evidence assessment prompt."""

from app.falsify.prompts import system_prompt  # noqa: F401

EVIDENCE_SYSTEM_ROLE = "evidence assessment"

EVIDENCE_ASSESSMENT_PROMPT = """Assess one retrieved source against a claim under adversarial verification.

CLAIM:
\"\"\"{claim}\"\"\"

SOURCE:
- title: {title}
- publisher: {publisher}
- url: {url}
- publication_date: {publication_date}
- retrieved text (may be truncated):
\"\"\"
{text}
\"\"\"

Answer strictly from the text above:
1. supports_claim: does this source provide positive evidence FOR the claim as stated?
2. contradicts_claim: does it provide evidence that the claim (as stated) is FALSE?
   - A source that merely discusses the same topic is NOT a contradiction.
   - Rounding-compatible numbers (e.g. 19.8% vs "about 20%") are support, not contradiction,
     unless the claim asserts exact precision.
3. relevance_score 0..1: how on-point is this source for the specific claim?
4. temporal_validity 0..1: is it current enough to judge the claim (consider the claim's time period
   and whether newer restatements could exist)?
5. is_direct: does the source address the claim's exact assertion (true) or only allow an inference (false)?
6. observed_value: if the source states a concrete number/date/fact about the claim's subject, quote it verbatim.

Rules:
- Do NOT assume the claim is true, and do NOT assume the source is true.
- Judge only what the quoted text actually says. Do not use outside knowledge to fill gaps.
- If the text says nothing relevant, all stances are false and relevance is near 0.

Return JSON:
{{
  "supports_claim": false,
  "contradicts_claim": false,
  "relevance_score": 0.0,
  "temporal_validity": 1.0,
  "is_direct": false,
  "observed_value": null,
  "reasoning": "1-3 sentences citing the specific passage relied on"
}}"""


def build(claim_text: str, title: str, publisher: str, url: str, publication_date: str | None, text: str) -> str:
    return EVIDENCE_ASSESSMENT_PROMPT.format(
        claim=claim_text,
        title=title or "(unknown)",
        publisher=publisher or "(unknown)",
        url=url,
        publication_date=publication_date or "(unknown)",
        text=text[:6000],
    )
