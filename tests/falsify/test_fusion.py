"""Tests for evidence fusion: deduplication, independence, weighting, coverage."""

from __future__ import annotations

import pytest

from app.falsify.analysis.evidence import EvidenceAnalyzer
from app.falsify.fusion.evidence_fusion import EvidenceFusion, normalize_url, text_similarity
from app.falsify.models import SearchQuery
from app.falsify.normalization.normalizer import ClaimNormalizer
from tests.conftest import make_evidence

CLAIM_TEXT = "Company X revenue increased by 20% in 2025."


@pytest.fixture
def normalizer(config):
    return ClaimNormalizer(config)


@pytest.fixture
def analyzer(config):
    return EvidenceAnalyzer(config)


@pytest.fixture
def fusion(config):
    return EvidenceFusion(config)


def _fuse(fusion, analyzer, normalizer, evidence, queries=None):
    claim = normalizer.normalize(CLAIM_TEXT)
    assessments = [analyzer.assess(claim, ev) for ev in evidence]
    return fusion.fuse(
        claim=claim,
        hypotheses=[],
        queries=queries or [],
        evidence=evidence,
        assessments=assessments,
    )


class TestUrlNormalization:
    def test_strips_www_and_fragment(self):
        assert normalize_url("https://WWW.Example.com/Path/") == normalize_url("https://example.com/path")

    def test_ignores_tracking_params(self):
        a = normalize_url("https://example.com/article?id=5&utm_source=twitter")
        b = normalize_url("https://example.com/article?id=5")
        assert a == b


class TestDuplicateDetection:
    def test_three_copies_count_as_one_voice(self, fusion, analyzer, normalizer):
        """Three low-quality blogs copying the same text must not outweigh one primary source."""
        copy_text = "Company X revenue increased 20% in 2025, amazing growth everyone is talking about."
        copies = [
            make_evidence(url=f"https://blog{i}.blogspot.com/post", title="Copy", text=copy_text,
                          publication_date="2026-01-01")
            for i in range(3)
        ]
        primary = make_evidence(
            url="https://www.sec.gov/companyx-10k", title="Company X 10-K",
            text="Company X annual filing: total revenue increased 20% in fiscal 2025 versus fiscal 2024.",
            publisher="SEC", publication_date="2026-02-01",
        )
        summary, clusters = _fuse(fusion, analyzer, normalizer, copies + [primary])
        # 3 identical copies collapse into 1 cluster; primary is another -> 2 supporting clusters
        assert summary.duplicated_evidence_detected >= 2
        assert summary.independent_supporting_clusters == 2

    def test_same_url_deduplicated(self, fusion, analyzer, normalizer):
        ev1 = make_evidence(url="https://reuters.com/article-1", title="R", text="Company X revenue increased 20% in 2025.", publication_date="2026-01-01")
        ev2 = make_evidence(url="https://reuters.com/article-1?utm=x", title="R", text="Company X revenue increased 20% in 2025.", publication_date="2026-01-01")
        summary, clusters = _fuse(fusion, analyzer, normalizer, [ev1, ev2])
        assert summary.independent_supporting_clusters == 1


class TestWeighting:
    def test_quality_weights_matter(self, fusion, analyzer, normalizer):
        gov = make_evidence(
            url="https://www.sec.gov/filing", title="Official filing",
            text="Company X revenue increased 20% in 2025 per audited results.", publication_date="2026-02-01",
        )
        blog = make_evidence(
            url="https://xblog.medium.com/post", title="Blog",
            text="Company X revenue increased 20% in 2025 apparently.", publication_date="2026-01-01",
        )
        claim = normalizer.normalize(CLAIM_TEXT)
        a_gov = analyzer.assess(claim, gov)
        a_blog = analyzer.assess(claim, blog)
        w_gov = fusion._weight(a_gov)
        w_blog = fusion._weight(a_blog)
        assert w_gov > w_blog

    def test_irrelevant_evidence_zero_weight(self, fusion, analyzer, normalizer):
        claim = normalizer.normalize(CLAIM_TEXT)
        ev = make_evidence(url="https://food.example", title="Recipes", text="Soup recipes increased 20% this year.", publication_date="2026-01-01")
        assert fusion._weight(analyzer.assess(claim, ev)) == 0.0


class TestAggregation:
    def test_support_and_contradict_strengths(self, fusion, analyzer, normalizer):
        supporting = make_evidence(
            url="https://www.sec.gov/s", title="Filing",
            text="Company X revenue increased 20% in 2025.", publication_date="2026-02-01",
        )
        contradicting = make_evidence(
            url="https://www.reuters.com/c", title="Reuters",
            text="Company X revenue declined 3% in 2025.", publication_date="2026-02-01",
        )
        summary, _ = _fuse(fusion, analyzer, normalizer, [supporting, contradicting])
        assert summary.supporting_evidence == 1
        assert summary.contradicting_evidence == 1
        assert summary.support_strength > 0
        assert summary.contradict_strength > 0
        assert summary.max_support_quality > summary.max_contradict_quality  # SEC > Reuters tier

    def test_coverage_counts_hypotheses_with_evidence(self, config, fusion, analyzer, normalizer):
        from app.falsify.models import FalsificationHypothesis, HypothesisCategory

        claim = normalizer.normalize(CLAIM_TEXT)
        hyp = FalsificationHypothesis(
            claim_id=claim.claim_id, category=HypothesisCategory.NUMERICAL,
            hypothesis="h", rationale="r", falsification_target="t",
        )
        query = SearchQuery(hypothesis_id=hyp.hypothesis_id, claim_id=claim.claim_id, query="q")
        ev = make_evidence(
            url="https://www.sec.gov/cov", title="Filing",
            text="Company X revenue increased 20% in 2025.", publication_date="2026-02-01",
        )
        ev.query_id = query.query_id
        assessments = [analyzer.assess(claim, ev)]
        summary, _ = fusion.fuse(
            claim=claim, hypotheses=[hyp], queries=[query], evidence=[ev], assessments=assessments
        )
        assert summary.hypotheses_total == 1
        assert summary.hypotheses_with_evidence == 1
        assert summary.coverage == pytest.approx(1.0)


class TestTextSimilarity:
    def test_identical_texts(self):
        assert text_similarity("revenue grew twenty percent", "revenue grew twenty percent") == 1.0

    def test_unrelated_texts(self):
        assert text_similarity("revenue grew twenty percent", "pancake recipe with maple syrup") < 0.2
