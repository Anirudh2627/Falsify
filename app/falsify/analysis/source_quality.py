"""Source quality scoring.

Tier model (per the product spec):

* **Tier 1** -- government, official filings/regulators, academic publishers,
  primary datasets (``.gov``, ``sec.gov``, ``.edu``, nature.com, who.int, ...)
* **Tier 2** -- reputable journalism and established research organizations
  (Reuters, AP, BBC, FT, Bloomberg, ...)
* **Tier 3** -- blogs, aggregators, forums, social media

Design principle enforced here and downstream: **a Tier 1 source is never
automatically 'correct'** -- quality is one weighted factor in evidence
evaluation, not proof.  Scores therefore stay below 1.0 and are combined
with relevance, temporal validity and independence in the fusion stage.
"""

from __future__ import annotations

import re

from app.falsify.models import SourceTier

# domain suffix -> tier (checked against the registrable domain and full host)
_TIER1_SUFFIXES = (".gov", ".edu", ".ac.uk", ".edu.au", ".mil", ".int")

_TIER1_DOMAINS = {
    "sec.gov", "federalreserve.gov", "bls.gov", "bea.gov", "census.gov", "data.gov",
    "imf.org", "worldbank.org", "oecd.org", "un.org", "who.int", "europa.eu",
    "ecb.europa.eu", "eurostat.ec.europa.eu", "nature.com", "science.org", "cell.com",
    "thelancet.com", "nejm.org", "arxiv.org", "doi.org", "ncbi.nlm.nih.gov",
    "pubmed.ncbi.nlm.nih.gov", "springer.com", "link.springer.com", "wiley.com",
    "tandfonline.com", "jstor.org", "ssrn.com", "ieee.org", "acm.org", "nasa.gov",
    "esa.int", "noaa.gov", "nielsen.com", "gartner.com",
}

_TIER2_DOMAINS = {
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "nytimes.com", "wsj.com",
    "ft.com", "bloomberg.com", "economist.com", "theguardian.com", "washingtonpost.com",
    "cnn.com", "npr.org", "france24.com", "dw.com", "aljazeera.com", "financialpost.com",
    "cnbc.com", "marketwatch.com", "businessinsider.com", "forbes.com", "time.com",
    "politico.com", "axios.com", "propublica.org", "technologyreview.com",
    "arstechnica.com", "theverge.com", "wired.com", "scientificamerican.com",
    "newscientist.com", "usatoday.com", "latimes.com", "spiegel.de", "lemonde.fr",
    "nydailynews.com", "pbs.org", "abc.net.au", "cbsnews.com", "nbcnews.com",
    "wikipedia.org", "en.wikipedia.org", "britannica.com", "pewresearch.org",
    "brookings.edu", "mckinsey.com", "deloitte.com", "statista.com", "s&p global",
    "spglobal.com", "moodys.com", "fitchratings.com",
}

_TIER3_DOMAINS = {
    "reddit.com", "quora.com", "twitter.com", "x.com", "facebook.com", "instagram.com",
    "tiktok.com", "youtube.com", "medium.com", "substack.com", "blogspot.com",
    "wordpress.com", "tumblr.com", "pinterest.com", "linkedin.com", "msn.com",
    "yahoo.com", "aol.com", "buzzfeed.com", "dailymail.co.uk", "newsmax.com",
    "breitbart.com", "huffpost.com", "vice.com", "threads.net", "discord.com",
    "4chan.org", "telegram.org", "t.me", "vk.com", "weibo.com",
}

_SCORES = {
    SourceTier.TIER_1: 0.9,
    SourceTier.TIER_2: 0.7,
    SourceTier.TIER_3: 0.35,
    SourceTier.UNKNOWN: 0.5,
}

_WIKIPEDIA_SCORE = 0.55  # tertiary source: better than blogs, not journalism


class SourceQualityScorer:
    """Deterministic domain/publisher-based source quality scorer."""

    def score(self, *, domain: str = "", url: str = "", publisher: str = "", text: str = "") -> tuple[float, SourceTier]:
        """Return ``(quality_score, tier)`` for a source.

        ``domain`` should already be normalized (lowercase, no ``www.``).
        """
        domain = (domain or "").lower().strip()
        if not domain and url:
            from app.falsify.retrieval.base import extract_domain

            domain = extract_domain(url)
        publisher_l = (publisher or "").lower()

        tier = self._tier_for(domain, publisher_l)
        score = _SCORES[tier]

        if domain.endswith("wikipedia.org"):
            score = _WIKIPEDIA_SCORE

        # small adjustments from content signals (never crossing a full tier)
        lowered_head = (text or "")[:2000].lower()
        if tier == SourceTier.UNKNOWN:
            if re.search(r"\b(annual report|10-k|10-q|form 8-k|official filing|press release)\b", lowered_head):
                score = min(0.75, score + 0.15)
            elif re.search(r"\b(peer[- ]reviewed|doi:|et al\.|abstract)\b", lowered_head):
                score = min(0.8, score + 0.2)
        if re.search(r"\b(sponsored content|advertisement|opinion|editorial|blog)\b", lowered_head) and tier != SourceTier.TIER_1:
            score = max(0.2, score - 0.1)

        return round(min(1.0, max(0.0, score)), 3), tier

    def _tier_for(self, domain: str, publisher_l: str) -> SourceTier:
        if not domain and not publisher_l:
            return SourceTier.UNKNOWN

        # exact / suffix match on the domain
        if domain:
            if domain in _TIER3_DOMAINS or any(domain.endswith("." + d) for d in _TIER3_DOMAINS):
                return SourceTier.TIER_3
            if domain in _TIER1_DOMAINS or any(domain == d or domain.endswith("." + d) for d in _TIER1_DOMAINS):
                return SourceTier.TIER_1
            if any(domain.endswith(suffix) for suffix in _TIER1_SUFFIXES):
                return SourceTier.TIER_1
            if domain in _TIER2_DOMAINS or any(domain.endswith("." + d) for d in _TIER2_DOMAINS):
                return SourceTier.TIER_2
            registrable = self._registrable(domain)
            if registrable in _TIER2_DOMAINS:
                return SourceTier.TIER_2

        # publisher-name fallback (when URL gives no signal)
        if publisher_l:
            for known, tier in (
                (_TIER1_DOMAINS, SourceTier.TIER_1),
                (_TIER2_DOMAINS, SourceTier.TIER_2),
                (_TIER3_DOMAINS, SourceTier.TIER_3),
            ):
                for d in known:
                    stem = d.split(".")[0]
                    if len(stem) > 3 and stem in publisher_l:
                        return tier
        return SourceTier.UNKNOWN

    @staticmethod
    def _registrable(domain: str) -> str:
        parts = domain.split(".")
        if len(parts) >= 3 and parts[-2] in {"co", "com", "org", "net", "gov", "edu", "ac"}:
            return ".".join(parts[-3:])
        return ".".join(parts[-2:]) if len(parts) >= 2 else domain

    @staticmethod
    def tier_label(tier: SourceTier) -> str:
        return {
            SourceTier.TIER_1: "Tier 1 (primary/authoritative)",
            SourceTier.TIER_2: "Tier 2 (reputable secondary)",
            SourceTier.TIER_3: "Tier 3 (blog/aggregator/social)",
            SourceTier.UNKNOWN: "Unknown source",
        }[tier]
