"""Deterministic claim normalization.

Transforms messy natural-language claims into a structured :class:`Claim`.
The layer is primarily *deterministic* (regex + lexicons); an LLM may be
injected to refine the result, but the pipeline is fully functional without
one, and the original text is always preserved.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from app.falsify.config import EngineConfig
from app.falsify.exceptions import ClaimValidationError, LLMError
from app.falsify.llm.base import LLMProvider
from app.falsify.llm.provider import NullLLM
from app.falsify.logging_utils import log_event
from app.falsify.models import Claim, ClaimKind, QuantitativeConstraint
from app.falsify.prompts import normalization as prompts

# ---------------------------------------------------------------------------
# Lexicons
# ---------------------------------------------------------------------------

_INCREASE_WORDS = {
    "increased", "increase", "increases", "grew", "grow", "growth", "grown",
    "rose", "rise", "rises", "risen", "climbed", "climb", "climbs", "jumped",
    "jump", "surged", "surge", "soared", "soar", "expanded", "expand",
    "expands", "doubled", "double", "tripled", "triple", "gained", "gain",
    "gains", "up", "higher", "raised", "raise", "raises", "boosted", "boost",
    "outpaced", "outperformed", "exceeded", "beat",
}

_DECREASE_WORDS = {
    "decreased", "decrease", "decreases", "declined", "decline", "declines",
    "fell", "fall", "falls", "fallen", "dropped", "drop", "drops", "plunged",
    "plunge", "plunges", "slumped", "slump", "shrank", "shrink", "shrinks",
    "contracted", "contract", "contracts", "reduced", "reduce", "reduces",
    "lowered", "lower", "lost", "lose", "loses", "down", "sank", "halved",
    "underperformed", "missed",
}

_CAUSAL_WORDS = {
    "causes", "cause", "caused", "causing", "leads", "lead", "led", "leading",
    "results", "result", "resulted", "resulting", "drives", "drive", "drove",
    "driving", "triggers", "trigger", "triggered", "produces", "produce",
    "produced", "because", "due", "thanks", "enables", "enable", "enabled",
    "makes", "make", "made",
}

_COMPARATIVE_WORDS = {
    "larger", "smaller", "bigger", "greater", "less", "more", "fewer",
    "higher", "lower", "better", "worse", "than", "compared", "versus", "vs",
    "exceeds", "surpasses", "outnumber",
}

_ATTRIBUTION_WORDS = {
    "said", "says", "stated", "states", "claimed", "claims", "announced",
    "announces", "reported", "reports", "told", "according", "wrote",
    "published", "argued", "argues",
}

_FUTURE_WORDS = {
    "will", "would", "shall", "expected", "expects", "expect", "forecast",
    "forecasts", "predicted", "predicts", "predict", "projects", "project",
    "projected", "anticipated", "estimates", "estimated", "likely", "poised",
    "set", "going",
}

_NEGATION_WORDS = {"not", "never", "no", "n't", "none", "neither", "nor", "without", "isn't", "aren't", "wasn't", "weren't", "doesn't", "don't", "didn't", "cannot", "can't", "won't"}

_ORG_SUFFIXES = {
    "inc", "inc.", "llc", "ltd", "ltd.", "corp", "corp.", "corporation",
    "company", "co", "co.", "plc", "gmbh", "s.a.", "sa", "ag", "nv", "bv",
    "group", "holdings", "technologies", "technology", "motors", "labs",
    "institute", "university", "foundation", "association", "bank", "airlines",
}

_METRICS = [
    "revenue", "sales", "profit", "earnings", "income", "gdp", "market cap",
    "market share", "valuation", "price", "cost", "costs", "spending",
    "investment", "population", "users", "subscribers", "customers",
    "temperature", "emissions", "unemployment", "inflation", "growth rate",
    "debt", "loss", "losses", "margin", "cash flow", "shipments", "deliveries",
    "wage", "wages", "salary", "rating", "score", "speed", "distance", "age",
]

_PREDICATE_VERBS = sorted(
    (_INCREASE_WORDS | _DECREASE_WORDS | _CAUSAL_WORDS | {"is", "are", "was", "were", "orbits", "orbit",
     "launched", "launch", "acquired", "acquire", "merged", "won", "win", "died", "born", "located",
     "headquartered", "developed", "created", "discovered", "invented", "signed", "approved", "banned",
     "elected", "appointed", "reached", "hit", "topped", "owns", "own", "operates", "operate",
     "said", "says", "stated", "states", "announced", "announces", "reported", "reports", "claimed",
     "claims", "told", "wrote", "deliver", "delivered", "delivers", "hired", "hires", "hire",
     "visited", "visit", "visits", "employs", "employed", "employ"})
    - {"up", "down", "set", "going", "no"},
    key=len,
    reverse=True,
)

_MONTHS = (
    "january|february|march|april|may|june|july|august|september|october|november|december"
)

_GEOGRAPHIC = {
    # countries / major regions (illustrative gazetteer, extensible)
    "united states", "usa", "us", "u.s.", "china", "india", "russia", "japan", "germany",
    "france", "uk", "u.k.", "united kingdom", "britain", "england", "canada", "brazil",
    "mexico", "italy", "spain", "netherlands", "switzerland", "sweden", "norway", "denmark",
    "finland", "poland", "turkey", "south korea", "korea", "australia", "new zealand",
    "indonesia", "thailand", "vietnam", "philippines", "malaysia", "singapore", "pakistan",
    "bangladesh", "egypt", "nigeria", "kenya", "south africa", "saudi arabia", "uae",
    "israel", "iran", "iraq", "argentina", "chile", "colombia", "peru", "ukraine",
    "belgium", "austria", "greece", "portugal", "ireland", "iceland", "hungary",
    "czech republic", "romania", "california", "texas", "new york", "florida", "europe",
    "asia", "africa", "north america", "south america", "antarctica", "global", "worldwide",
    "world", "mars", "moon", "solar system", "milky way",
}

_CURRENCIES = {
    "$": "USD", "us$": "USD", "usd": "USD", "€": "EUR", "eur": "EUR", "£": "GBP",
    "gbp": "GBP", "¥": "JPY", "jpy": "JPY", "₹": "INR", "inr": "INR", "chf": "CHF",
    "r$": "BRL", "brl": "BRL",
}

_MAGNITUDES = {
    "thousand": 1e3, "k": 1e3, "million": 1e6, "m": 1e6, "mm": 1e6,
    "billion": 1e9, "b": 1e9, "bn": 1e9, "trillion": 1e12, "t": 1e12,
}

_COMPARATORS = {
    "exactly": "exactly",
    "precisely": "exactly",
    "at least": "at_least",
    "no less than": "at_least",
    "more than": "more_than",
    "over": "more_than",
    "above": "more_than",
    "less than": "less_than",
    "under": "less_than",
    "below": "less_than",
    "approximately": "approximately",
    "about": "approximately",
    "around": "approximately",
    "roughly": "approximately",
    "nearly": "approximately",
    "almost": "approximately",
}

# ---------------------------------------------------------------------------
# Regexes
# ---------------------------------------------------------------------------

_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
_QUARTER_RE = re.compile(r"\b[Qq]([1-4])\s*(19\d{2}|20\d{2})?\b")
_MONTH_RE = re.compile(rf"\b({_MONTHS})\s+(19\d{{2}}|20\d{{2}})?\b", re.IGNORECASE)
_RELATIVE_DATE_RE = re.compile(
    r"\b(last|this|next|the past|the coming)\s+(year|month|quarter|week|decade|"
    r"january|february|march|april|may|june|july|august|september|october|november|december)\b",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")
_PERCENT_RE = re.compile(r"([-+]?\d[\d,]*(?:\.\d+)?)\s*(%|percent(?:age points)?|pp)(?![a-z])", re.IGNORECASE)
_CURRENCY_RE = re.compile(
    r"(us\$|\$|€|£|¥|₹|r\$)\s?([-+]?\d[\d,]*(?:\.\d+)?)\s*(thousand|million|billion|trillion|k|m|bn|b|t)?\b",
    re.IGNORECASE,
)
_PROPER_NOUN_RE = re.compile(r"\b([A-Z][A-Za-z0-9&.\-']*(?:\s+[A-Z][A-Za-z0-9&.\-']*)*)\b")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?;])\s+(?=[A-Z0-9\"'(])")

# Common words that are frequently capitalized only because they start a
# sentence (or appear in titles) and must NOT be treated as named entities.
_COMMON_NON_ENTITY_WORDS = {
    "the", "a", "an", "this", "that", "these", "those", "it", "its", "there", "here",
    "however", "moreover", "furthermore", "also", "although", "because", "but", "and",
    "or", "if", "when", "while", "after", "before", "during", "then", "now", "today",
    "yesterday", "tomorrow", "he", "she", "they", "we", "you", "his", "her", "their",
    "our", "your", "my", "him", "them", "us", "official", "officials", "company",
    "companies", "analyst", "analysts", "researcher", "researchers", "scientist",
    "scientists", "according", "report", "reports", "reporting", "study", "studies",
    "data", "result", "results", "revenue", "sales", "profit", "profits", "earnings",
    "income", "growth", "inflation", "unemployment", "market", "markets", "government",
    "people", "person", "user", "users", "customer", "customers", "share", "shares",
    "stock", "stocks", "price", "prices", "cost", "costs", "both", "many", "most",
    "some", "all", "each", "every", "new", "old", "other", "another", "few", "several",
    "various", "source", "sources", "evidence", "president", "minister", "ministers",
    "ceo", "cfo", "gdp", "gnp", "cpi", "ppi", "eps", "roe", "kpi", "gmv", "total",
    "annual", "quarterly", "monthly", "yearly", "global", "national", "local",
    "recession", "pandemic", "war", "election", "elections", "vote", "survey",
    "temperature", "emissions", "population", "spending", "investment", "debt",
    "loss", "losses", "margin", "cash", "flow", "shipments", "deliveries", "wage",
    "wages", "salary", "rating", "score", "speed", "distance", "age", "warning",
    "update", "announcement", "statement", "news", "press", "release", "filing",
    "filings", "document", "documents", "record", "records", "figure", "figures",
    "number", "numbers", "percent", "percentage", "billion", "million", "thousand",
    "trillion", "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december", "monday", "tuesday",
    "wednesday", "thursday", "friday", "saturday", "sunday", "spring", "summer",
    "autumn", "fall", "winter", "north", "south", "east", "west", "true", "false",
    "why", "how", "what", "who", "whom", "whose", "which", "where", "center",
    "centre", "middle", "top", "bottom", "high", "low", "big", "large", "small",
    "major", "minor", "key", "main", "primary", "secondary", "public", "private",
    "social", "media", "internet", "web", "ai", "tech", "technology", "science",
    "health", "medicine", "energy", "oil", "gas", "power", "water", "food",
    "i", "is", "are", "was", "were", "be", "been", "being", "am", "do", "does",
    "did", "has", "have", "had", "will", "would", "shall", "should", "can",
    "could", "must", "might", "not", "no", "yes", "of", "to", "in", "on",
    "at", "by", "for", "with", "from", "into", "onto", "over", "under", "than",
    "versus", "via", "per", "about", "around", "nearly", "almost", "roughly",
    "approximately", "exactly", "precisely", "just", "only", "even", "still",
    "again", "once", "twice", "never", "always", "often", "sometimes", "rarely",
    "increased", "decreased", "grew", "declined", "rose", "fell", "causes", "caused",
    "said", "says", "solar", "system", "climate", "change", "vaccine", "vaccines",
    "cancer", "disease", "death", "deaths", "birth", "births", "crime", "poverty",
}


def _predicate_in_text(predicate: str, lowered_text: str) -> bool:
    """Word-boundary predicate match with light stemming (orbit/orbits/orbiting)."""
    p = predicate.lower().strip("'")
    if not p:
        return False
    if len(p) <= 3:
        return re.search(rf"\b{re.escape(p)}\b", lowered_text) is not None
    stem = re.sub(r"(ing|ed|es|s)$", "", p)
    stem = stem if len(stem) >= 3 else p
    return re.search(rf"\b{re.escape(stem)}", lowered_text) is not None


def _last_word_pos(window: str, word: str) -> int:
    """Position of the last whole-word occurrence of ``word`` in ``window``, or -1."""
    last = -1
    for match in re.finditer(rf"\b{re.escape(word)}\b", window):
        last = match.start()
    return last


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9$%€£]+(?:'[a-z]+)?", text.lower())


def _implied_precision(raw: str) -> float | None:
    """Rounding tolerance implied by how a number was written.

    '20%' implies +/-0.5, '20.0%' implies +/-0.05, '21.7%' implies +/-0.05.
    """
    raw = raw.strip().replace(",", "")
    if "." in raw:
        decimals = len(raw.split(".", 1)[1])
        return 0.5 * (10 ** -decimals)
    return 0.5


def _parse_number(raw: str) -> float | None:
    try:
        return float(raw.replace(",", ""))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Normalizer
# ---------------------------------------------------------------------------


class ClaimNormalizer:
    """Deterministic-first claim normalizer with optional LLM refinement."""

    def __init__(self, config: EngineConfig | None = None, llm: LLMProvider | None = None) -> None:
        self._config = config or EngineConfig()
        self._llm = llm

    # -- public API ---------------------------------------------------------

    def normalize(self, text: str) -> Claim:
        log_event("claim_normalization_started", chars=len(text or "") if isinstance(text, str) else -1)
        if not isinstance(text, str):
            raise ClaimValidationError(
                f"Claim text must be a string, got {type(text).__name__}"
            )
        if not text.strip():
            raise ClaimValidationError("Claim text is empty")
        text = text.strip()
        if len(text) > self._config.max_claim_chars:
            raise ClaimValidationError(
                f"Claim too long ({len(text)} chars > {self._config.max_claim_chars})"
            )

        claim = self._normalize_deterministic(text)

        if self._llm is not None and not isinstance(self._llm, NullLLM) and self._config.use_llm_for_normalization:
            claim = self._refine_with_llm(claim, text)

        if not claim.normalized_text:
            claim.normalized_text = self._build_normalized_text(claim)

        log_event(
            "claim_normalized",
            claim_id=claim.claim_id,
            kind=claim.claim_kind.value,
            entities=len(claim.entities),
            quantities=len(claim.quantitative_constraints),
            source=claim.normalization_source,
        )
        return claim

    # -- deterministic extraction -------------------------------------------

    def _normalize_deterministic(self, text: str) -> Claim:
        lowered = text.lower()
        tokens = _tokens(text)
        token_set = set(tokens)

        entities = self._extract_entities(text, tokens)
        temporal = self._extract_temporal(text, lowered)
        geographic = self._extract_geographic(lowered)
        quantities = self._extract_quantities(lowered, entities)
        predicates = self._extract_predicates(tokens)

        negated = bool(token_set & _NEGATION_WORDS) or "n't" in lowered
        is_future = bool(token_set & _FUTURE_WORDS) or self._future_dates(temporal)

        claim_kind = self._classify(lowered, tokens, quantities, predicates, is_future)
        assertions = self._split_assertions(text)

        claim = Claim(
            original_text=text,
            normalized_text="",  # filled after possible LLM refinement
            claim_kind=claim_kind,
            entities=entities,
            predicates=predicates,
            temporal_constraints=temporal,
            geographic_constraints=geographic,
            quantitative_constraints=quantities,
            negated=negated,
            is_future_claim=is_future,
            assertions=assertions,
            normalization_source="deterministic",
        )
        claim.normalized_text = self._build_normalized_text(claim)
        return claim

    def _extract_entities(self, text: str, tokens: list[str]) -> list[str]:
        entities: list[str] = []

        # "Company X"-style placeholders
        for match in re.finditer(r"\b(company|firm|corp|organization)\s+([A-Z])\b", text):
            entities.append(f"{match.group(1).title()} {match.group(2)}")

        for match in _PROPER_NOUN_RE.finditer(text):
            phrase = match.group(1)
            phrase = re.sub(r"'s$", "", phrase)  # strip possessive: "Tesla's" -> "Tesla"
            words = [w for w in phrase.split() if w.lower() not in {"the", "a", "an", "of"}]
            if not words:
                continue
            phrase = " ".join(words)
            first = words[0].lower().rstrip("'")

            if len(words) == 1:
                # single-word candidate: drop common words & metric nouns,
                # keep single letters only as placeholders (X, Y, Z)
                if first in _COMMON_NON_ENTITY_WORDS:
                    continue
                if any(first == m or first in m.split() for m in _METRICS):
                    continue
                if len(first) <= 1 and first not in {"x", "y", "z"}:
                    continue
                if first.isdigit():
                    continue

            is_sentence_start = match.start() == 0 or text[: match.start()].rstrip().endswith(
                (".", "!", "?", ";", ":")
            )
            candidate = phrase
            if is_sentence_start and len(words) == 1 and words[0][0].isupper():
                candidate = words[0]
            if candidate.lower() in {e.lower() for e in entities}:
                continue
            entities.append(candidate.strip())

        # org-suffix patterns in lowercase text: "tesla inc" -> "Tesla Inc"
        for suffix in ("inc", "llc", "ltd", "corp", "plc", "gmbh"):
            for match in re.finditer(rf"\b([A-Za-z][A-Za-z0-9&.\-']*)\s+{suffix}\b", text, re.IGNORECASE):
                head = match.group(1)
                if head.lower() in _COMMON_NON_ENTITY_WORDS:
                    continue
                cand = f"{head} {suffix.upper() if suffix in ('inc', 'llc', 'ltd', 'corp', 'plc') else suffix}"
                if cand.lower() not in {e.lower() for e in entities}:
                    entities.append(cand)

        # dedupe case-insensitively (prefer the longer form), preserve order, cap
        seen: set[str] = set()
        unique: list[str] = []
        for entity in sorted(entities, key=len, reverse=True):
            key = entity.lower().strip()
            if key and key not in seen and not any(key in s for s in seen):
                seen.add(key)
                unique.append(entity.strip())
        unique.sort(key=lambda e: text.find(e.split()[0]) if text.find(e.split()[0]) >= 0 else 999)
        return unique[:10]

    def _extract_temporal(self, text: str, lowered: str) -> list[str]:
        found: list[str] = []
        for match in _QUARTER_RE.finditer(text):
            quarter = f"Q{match.group(1)}"
            year = match.group(2)
            found.append(f"{quarter} {year}" if year else quarter)
        for match in _MONTH_RE.finditer(text):
            month = match.group(1).title()
            year = match.group(2)
            found.append(f"{month} {year}" if year else month)
        for match in _YEAR_RE.finditer(text):
            year = match.group(1)
            if year not in found and not any(year in f for f in found):
                found.append(year)
        for match in _RELATIVE_DATE_RE.finditer(lowered):
            phrase = match.group(0)
            if phrase not in found:
                found.append(phrase)
        # ranges: 2020-2024, "between 2020 and 2024"
        for match in re.finditer(r"\b((?:19|20)\d{2})\s*(?:-|–|to|through)\s*((?:19|20)\d{2})\b", lowered):
            found.append(f"{match.group(1)}-{match.group(2)}")
        return found

    def _extract_geographic(self, lowered: str) -> list[str]:
        found: list[str] = []
        for place in sorted(_GEOGRAPHIC, key=len, reverse=True):
            pattern = rf"\b{re.escape(place)}\b"
            if re.search(pattern, lowered):
                if place in {"us", "u.s.", "usa"} and "united states" in found:
                    continue
                if not any(place in f for f in found):
                    found.append(place)
        return found[:6]

    def _extract_quantities(self, lowered: str, entities: list[str]) -> list[QuantitativeConstraint]:
        quantities: list[QuantitativeConstraint] = []

        # direction near the number (search a window before each match)
        def _direction_and_metric(start: int) -> tuple[str | None, str | None, str | None]:
            window = lowered[max(0, start - 90) : start]
            direction: str | None = None
            best_pos = -1
            for word in _INCREASE_WORDS:
                pos = _last_word_pos(window, word)
                if pos > best_pos:
                    best_pos, direction = pos, "increased"
            for word in _DECREASE_WORDS:
                pos = _last_word_pos(window, word)
                if pos > best_pos:
                    best_pos, direction = pos, "decreased"
            metric: str | None = None
            metric_pos = -1
            for candidate in sorted(_METRICS, key=len, reverse=True):
                pos = _last_word_pos(window, candidate)
                if pos > metric_pos:
                    metric_pos, metric = pos, candidate
            comparator: str | None = None
            for phrase, canonical in sorted(_COMPARATORS.items(), key=lambda kv: len(kv[0]), reverse=True):
                if re.search(rf"\b{re.escape(phrase)}\b", window):
                    comparator = canonical
                    break
            return direction, metric, comparator

        for match in _PERCENT_RE.finditer(lowered):
            raw = match.group(1)
            value = _parse_number(raw)
            direction, metric, comparator = _direction_and_metric(match.start())
            baseline = self._find_baseline(lowered, match.end())
            quantities.append(
                QuantitativeConstraint(
                    metric=metric,
                    raw_value=f"{raw}%",
                    value=value,
                    unit="percent",
                    direction=direction,
                    comparator=comparator,
                    comparison_baseline=baseline,
                    implied_precision=_implied_precision(raw),
                )
            )

        for match in _CURRENCY_RE.finditer(lowered):
            symbol, raw, magnitude = match.group(1), match.group(2), match.group(3)
            value = _parse_number(raw)
            unit = _CURRENCIES.get(symbol.lower(), symbol)
            if magnitude:
                mult = _MAGNITUDES.get(magnitude.lower())
                if mult and value is not None:
                    value *= mult
            direction, metric, comparator = _direction_and_metric(match.start())
            quantities.append(
                QuantitativeConstraint(
                    metric=metric or ("amount",)[0],
                    raw_value=match.group(0).strip(),
                    value=value,
                    unit=unit,
                    direction=direction,
                    comparator=comparator,
                    comparison_baseline=self._find_baseline(lowered, match.end()),
                    implied_precision=_implied_precision(raw),
                )
            )

        # bare numbers with direction but no unit (e.g. "users doubled to 5")
        if not quantities:
            for match in _NUMBER_RE.finditer(lowered):
                if _YEAR_RE.fullmatch(match.group(0)):
                    continue
                direction, metric, comparator = _direction_and_metric(match.start())
                if direction and metric:
                    quantities.append(
                        QuantitativeConstraint(
                            metric=metric,
                            raw_value=match.group(0),
                            value=_parse_number(match.group(0)),
                            unit=None,
                            direction=direction,
                            comparator=comparator,
                            comparison_baseline=self._find_baseline(lowered, match.end()),
                            implied_precision=_implied_precision(match.group(0)),
                        )
                    )
                    break
        return quantities

    def _find_baseline(self, lowered: str, after_pos: int) -> str | None:
        tail = lowered[after_pos : after_pos + 80]
        match = re.search(
            r"\b(?:than|vs\.?|versus|compared with|compared to|over|from)\s+(?:in\s+)?"
            r"((?:19|20)\d{2}|last year|the prior year|the previous year)\b",
            tail,
        )
        if match:
            return match.group(1)
        match = re.search(r"\b(year[- ]over[- ]year|yoy|y/y|annually|quarter[- ]over[- ]quarter|qoq)\b", tail)
        if match:
            return match.group(0)
        return None

    def _extract_predicates(self, tokens: list[str]) -> list[str]:
        predicates: list[str] = []
        for token in tokens:
            base = token.rstrip("'")
            if base in _PREDICATE_VERBS and base not in predicates:
                predicates.append(base)
        return predicates[:8]

    def _classify(
        self,
        lowered: str,
        tokens: list[str],
        quantities: list[QuantitativeConstraint],
        predicates: list[str],
        is_future: bool,
    ) -> ClaimKind:
        token_set = set(tokens)
        # causal markers dominate everything else
        if token_set & {"causes", "cause", "caused", "causing", "leads", "led", "results", "resulted", "drives", "drove", "triggers", "triggered", "because"}:
            return ClaimKind.CAUSAL
        # attribution only when there is no concrete quantity (otherwise the
        # numeric assertion is the testable core of the claim)
        if (token_set & _ATTRIBUTION_WORDS) and not quantities:
            return ClaimKind.ATTRIBUTION
        if is_future:
            return ClaimKind.FUTURE
        if quantities:
            if any(q.direction for q in quantities):
                return ClaimKind.QUANTITATIVE_CHANGE
            return ClaimKind.QUANTITATIVE_STATE
        if token_set & {"than", "versus", "vs", "compared"} or (token_set & _COMPARATIVE_WORDS and len(token_set & _COMPARATIVE_WORDS) >= 2):
            return ClaimKind.COMPARATIVE
        return ClaimKind.FACTUAL

    def _future_dates(self, temporal: list[str]) -> bool:
        now_year = datetime.now(UTC).year
        for item in temporal:
            match = _YEAR_RE.search(item)
            if match and int(match.group(1)) > now_year:
                return True
            if item.lower().startswith("next"):
                return True
        return False

    def _split_assertions(self, text: str) -> list[str]:
        parts = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
        # also split on "and" joining two verb phrases in a single sentence
        assertions: list[str] = []
        for part in parts:
            sub = re.split(r"\s+and\s+(?=[A-Z]|\w+\s+(?:is|are|was|were|has|have|had|will|increased|decreased|grew|declined))", part)
            assertions.extend(s.strip(" .") for s in sub if s.strip(" ."))
        return [a for a in assertions if a][:5] or [text]

    def _build_normalized_text(self, claim: Claim) -> str:
        """Compose a canonical restatement from the extracted slots."""
        pieces: list[str] = []
        entity = claim.primary_entity or "The subject"
        q = claim.primary_quantity
        if q and q.metric:
            if q.direction == "increased":
                pieces.append(f"{entity}'s {q.metric} increased")
            elif q.direction == "decreased":
                pieces.append(f"{entity}'s {q.metric} decreased")
            else:
                pieces.append(f"{entity}'s {q.metric} was")
            pieces.append(f"by {q.raw_value}" if q.direction else f"{q.raw_value}")
            if q.comparison_baseline:
                pieces.append(f"relative to {q.comparison_baseline}")
            temporal = " ".join(claim.temporal_constraints[:2])
            if temporal:
                pieces.append(f"in {temporal}")
            geo = claim.geographic_constraints[:1]
            if geo:
                pieces.append(f"({geo[0]})")
        else:
            # no quantity: keep the (cleaned) original assertion order
            base = claim.assertions[0] if claim.assertions else claim.original_text
            return base.strip().rstrip(".") + "."
        text = " ".join(pieces).strip().rstrip(".") + "."
        return text[0].upper() + text[1:]

    # -- optional LLM refinement ---------------------------------------------

    def _refine_with_llm(self, claim: Claim, text: str) -> Claim:
        from app.falsify.llm.base import generate_json

        structure = (
            f"entities={claim.entities}; predicates={claim.predicates}; "
            f"temporal={claim.temporal_constraints}; geographic={claim.geographic_constraints}; "
            f"quantities={[q.model_dump() for q in claim.quantitative_constraints]}; "
            f"kind={claim.claim_kind.value}"
        )
        prompt = prompts.build(text) + f"\n\nCurrent deterministic extraction (correct it only if clearly wrong):\n{structure}"
        try:
            data = generate_json(
                self._llm,  # type: ignore[arg-type]
                prompt,
                system=prompts.system_prompt(prompts.NORMALIZATION_SYSTEM_ROLE),
                max_retries=self._config.llm_max_retries,
                stage="normalization",
            )
            if not isinstance(data, dict):
                raise LLMError("normalization payload is not an object")
        except (LLMError, Exception) as exc:  # LLM is advisory: fall back silently but log
            log_event("llm_normalization_skipped", reason=str(exc)[:160], level=30)
            return claim

        merged = claim.model_copy(deep=True)
        merged.normalization_source = "hybrid"

        def _merge_str_list(field: str, new_values: object) -> None:
            if isinstance(new_values, list):
                cleaned = [str(v).strip() for v in new_values if str(v).strip()]
                existing = {v.lower() for v in getattr(merged, field)}
                for value in cleaned:
                    if value.lower() not in existing:
                        getattr(merged, field).append(value)
                        existing.add(value.lower())

        _merge_str_list("entities", data.get("entities"))
        _merge_str_list("temporal_constraints", data.get("temporal_constraints"))
        _merge_str_list("geographic_constraints", data.get("geographic_constraints"))
        _merge_str_list("assertions", data.get("assertions"))

        kind = data.get("claim_kind")
        if isinstance(kind, str):
            try:
                merged.claim_kind = ClaimKind(kind.lower())
            except ValueError:
                merged.normalization_warnings.append(f"LLM returned unknown claim_kind {kind!r}")
        if isinstance(data.get("negated"), bool):
            merged.negated = merged.negated or data["negated"]
        if isinstance(data.get("is_future_claim"), bool):
            merged.is_future_claim = merged.is_future_claim or data["is_future_claim"]
        normalized = data.get("normalized_text")
        if isinstance(normalized, str) and normalized.strip():
            merged.normalized_text = normalized.strip()

        # quantitative constraints: prefer deterministic values, add LLM-only ones
        llm_quantities = data.get("quantitative_constraints")
        if isinstance(llm_quantities, list) and not merged.quantitative_constraints:
            for item in llm_quantities:
                if isinstance(item, dict):
                    try:
                        merged.quantitative_constraints.append(QuantitativeConstraint.model_validate(item))
                    except Exception:
                        merged.normalization_warnings.append("dropped malformed LLM quantitative constraint")
        return merged
