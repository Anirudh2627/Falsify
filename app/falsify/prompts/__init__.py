"""Prompt templates for the Falsify pipeline.

Prompts live here -- separate from Python business logic -- so they can be
reviewed, versioned and A/B tested without touching engine code.  Every
prompt shares the :data:`GUARDRAILS` block, which encodes Falsify's core
epistemic rules:

* Do NOT assume the claim is true.
* Actively look for what would make it false.
* Distinguish contradiction from mere irrelevance.
* Never manufacture evidence, citations or URLs.
"""

from __future__ import annotations

GUARDRAILS = """HARD RULES (never violate):
- Do NOT assume the claim is true. Treat it as an untrusted assertion.
- Actively reason about what evidence WOULD prove the claim false.
- Clearly distinguish a genuine contradiction from irrelevant or merely tangential information.
- Do NOT manufacture evidence. Never invent citations, URLs, document names, dates or quotes.
- If you are unsure, say so via low scores / empty lists -- never by guessing.
- Respond ONLY with valid JSON matching the requested schema. No prose outside the JSON."""


def system_prompt(role: str) -> str:
    return (
        f"You are Falsify, an adversarial claim-verification engine. Current task: {role}\n\n"
        f"{GUARDRAILS}"
    )
