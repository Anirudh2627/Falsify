"""Tests for source quality scoring."""

from __future__ import annotations

from app.falsify.analysis.source_quality import SourceQualityScorer
from app.falsify.models import SourceTier


class TestTiering:
    def setup_method(self):
        self.scorer = SourceQualityScorer()

    def test_government_is_tier1(self):
        score, tier = self.scorer.score(domain="bls.gov")
        assert tier == SourceTier.TIER_1
        assert score >= 0.85

    def test_sec_filings_tier1(self):
        score, tier = self.scorer.score(url="https://www.sec.gov/Archives/edgar/data/1318605/0001")
        assert tier == SourceTier.TIER_1

    def test_academic_tier1(self):
        _, tier = self.scorer.score(domain="nature.com")
        assert tier == SourceTier.TIER_1
        _, tier = self.scorer.score(domain="cs.mit.edu")
        assert tier == SourceTier.TIER_1

    def test_reputable_journalism_tier2(self):
        for domain in ("reuters.com", "apnews.com", "ft.com", "bbc.com"):
            score, tier = self.scorer.score(domain=domain)
            assert tier == SourceTier.TIER_2, domain
            assert 0.6 <= score <= 0.8

    def test_subdomain_of_tier2(self):
        _, tier = self.scorer.score(domain="archive.nytimes.com")
        assert tier == SourceTier.TIER_2

    def test_social_and_forums_tier3(self):
        for domain in ("reddit.com", "x.com", "medium.com", "facebook.com"):
            score, tier = self.scorer.score(domain=domain)
            assert tier == SourceTier.TIER_3, domain
            assert score <= 0.45

    def test_unknown_domain_neutral(self):
        score, tier = self.scorer.score(domain="random-blog-xyz.example")
        assert tier == SourceTier.UNKNOWN
        assert 0.3 <= score <= 0.7

    def test_wikipedia_is_not_tier1(self):
        score, _ = self.scorer.score(domain="en.wikipedia.org")
        assert score < 0.7

    def test_publisher_fallback(self):
        _, tier = self.scorer.score(publisher="Reuters")
        assert tier == SourceTier.TIER_2


class TestQualityIsNotProof:
    def test_tier1_never_scores_certainty(self):
        score, _ = SourceQualityScorer().score(domain="sec.gov")
        assert score < 1.0  # quality is a weight, never proof

    def test_content_signal_adjusts_unknown_only(self):
        scorer = SourceQualityScorer()
        base, _ = scorer.score(domain="unknown.example")
        boosted, _ = scorer.score(domain="unknown.example", text="Excerpt from the official annual report (Form 10-K) filed by the company.")
        assert boosted > base
        # a tier3 source is not rescued by press-release language
        t3_base, _ = scorer.score(domain="blogspot.com")
        t3_boosted, _ = scorer.score(domain="blogspot.com", text="copy of a press release")
        assert t3_boosted <= t3_base + 1e-9
