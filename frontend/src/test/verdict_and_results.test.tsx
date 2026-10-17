import React from 'react';
import '@testing-library/jest-dom';
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { VerdictBadge } from '../components/VerdictBadge';
import { VerdictCard } from '../components/VerdictCard';
import { EvidenceList } from '../components/EvidenceList';
import { HypothesesPanel } from '../components/HypothesesPanel';
import { ContradictionsPanel } from '../components/ContradictionsPanel';
import { ReasoningTraceView } from '../components/ReasoningTraceView';
import { Verdict, VerificationResult } from '../types/falsify';

describe('Verdict and Results Components', () => {
  const verdicts: Verdict[] = ['VERIFIED', 'QUALIFIED', 'CONFLICTED', 'REFUTED', 'UNVERIFIABLE'];

  it.each(verdicts)('renders verdict badge for %s correctly', (verdict) => {
    const { container } = render(<VerdictBadge verdict={verdict} />);
    expect(screen.getByText(verdict)).toBeInTheDocument();
    expect(container.firstChild).toHaveClass('inline-flex');
  });

  it('renders unknown verdict safely without crashing', () => {
    render(<VerdictBadge verdict="UNKNOWN_STATE" />);
    expect(screen.getByText('UNKNOWN_STATE')).toBeInTheDocument();
  });

  it('renders VerdictCard with full metrics, confidence, and breakdown', () => {
    const mockResult: VerificationResult = {
      id: 101,
      claim_id: 'claim-101',
      claim_text: 'The moon orbits the Earth in approximately 27 days.',
      verdict: 'VERIFIED',
      confidence: 0.94,
      confidence_explanation: 'Multiple independent astronomical sources confirm orbital period.',
      confidence_breakdown: {
        evidence_quality: 0.95,
        evidence_relevance: 0.92,
        source_independence: 0.90,
        cross_source_agreement: 0.98,
        contradiction_strength: 0.05,
        temporal_validity: 0.90,
        retrieval_coverage: 0.95,
        decisiveness_margin: 0.89,
        weighted_total: 0.94,
      },
      evidence: [],
      hypotheses: [],
      contradictions: [],
      generated_queries: [],
      assessments: [],
      fusion_output: null,
      claim: {
        claim_id: 'claim-101',
        original_text: 'The moon orbits the Earth in approximately 27 days.',
        normalized_text: 'The moon orbits the Earth in approximately 27 days.',
        claim_kind: 'factual',
        entities: ['moon', 'Earth'],
        predicates: ['orbits'],
        temporal_constraints: [],
        geographic_constraints: [],
        quantitative_constraints: [],
      },
      queries: [],
      fusion: {
        total_evidence: 0,
        independent_clusters: 0,
        duplicate_clusters: 0,
        cluster_sizes: {},
        coverage_ratio: 1.0,
        direct_evidence_count: 0,
        indirect_evidence_count: 0,
      },
      errors: [],
      reasoning_trace: {
        claim: 'The moon orbits the Earth in approximately 27 days.',
        normalized_claim: 'The moon orbits the Earth in approximately 27 days.',
        claim_kind: 'factual',
        hypotheses: [],
        queries: [],
        evidence_summary: {},
        evidence: [],
        contradictions: [],
        verdict: 'VERIFIED',
        confidence: 0.94,
        confidence_explanation: 'Multiple independent astronomical sources confirm orbital period.',
        reasoning: '',
        errors: [],
        stage_timings_ms: { retrieval: 120 }
      },
      created_at: '2026-10-15T12:00:00Z',
    };

    render(<VerdictCard result={mockResult} />);

    expect(screen.getByText(/94%/i)).toBeInTheDocument();
    const explanationMatches = screen.getAllByText(/Multiple independent astronomical sources/i);
    expect(explanationMatches.length).toBeGreaterThan(0);
    expect(screen.getAllByText((_content, element) => element?.textContent?.trim() === '#101').length).toBeGreaterThan(0);
    expect(screen.getByText(/Evidence Quality/i)).toBeInTheDocument();
  });

  it('handles missing optional fields gracefully without crashing', () => {
    const sparseResult = {
      claim_text: 'Sparse claim',
      claim: {
        claim_id: 'claim-sparse',
        original_text: 'Sparse claim',
        normalized_text: 'Sparse claim',
        claim_kind: 'factual',
        entities: [],
        predicates: [],
        temporal_constraints: [],
        geographic_constraints: [],
        quantitative_constraints: [],
      },
      verdict: 'UNVERIFIABLE' as Verdict,
      confidence: 0.2,
      confidence_explanation: 'No evidence retrieved',
    } as unknown as VerificationResult;

    render(<VerdictCard result={sparseResult} />);
    expect(screen.getByText('UNVERIFIABLE')).toBeInTheDocument();
    expect(screen.getByText(/20%/i)).toBeInTheDocument();

    // Render EvidenceList with empty array
    render(<EvidenceList evidenceList={[]} />);
    expect(screen.getByText(/No evidence items matching/i)).toBeInTheDocument();

    // Render HypothesesPanel with empty arrays
    render(<HypothesesPanel hypotheses={[]} queries={[]} />);
    expect(screen.getByText(/Falsification Hypotheses & Adversarial Queries/i)).toBeInTheDocument();

    // Render ContradictionsPanel with empty array and null fusion
    render(<ContradictionsPanel contradictions={[]} fusion={null} />);
    expect(screen.getByText(/No factual contradictions/i)).toBeInTheDocument();

    // Render ReasoningTraceView with empty trace
    render(<ReasoningTraceView trace={undefined} fullResult={sparseResult} />);
    expect(screen.getByText(/Audit & Reasoning Trace/i)).toBeInTheDocument();
  });

  it('renders EvidenceList items with stance, tier, and secure external links', () => {
    const mockEvidence = [
      {
        evidence_id: 'ev-1',
        query_id: 'q-1',
        source_url: 'https://nasa.gov/moon-orbit',
        title: 'NASA Earth Satellite Dynamics',
        publisher: 'NASA',
        domain: 'nasa.gov',
        retrieved_text: 'The Moon completes an orbit around Earth in 27.3 days.',
        relevant_passages: ['The Moon completes an orbit around Earth in 27.3 days.'],
      },
    ];

    const mockAssessments = [
      {
        evidence_id: 'ev-1',
        supports_claim: true,
        contradicts_claim: false,
        stance: 'supporting',
        relevance_score: 0.98,
        source_quality_score: 0.95,
        source_tier: 1 as const,
        temporal_validity: 0.9,
        is_direct: true,
        reasoning: 'Direct astronomical measurement confirms orbital cycle.',
      },
    ];

    render(<EvidenceList evidenceList={mockEvidence} assessments={mockAssessments} />);

    expect(screen.getByText('NASA Earth Satellite Dynamics')).toBeInTheDocument();
    expect(screen.getByText(/The Moon completes an orbit around Earth/i)).toBeInTheDocument();
    expect(screen.getByText(/Tier 1 Primary \/ Regulatory/i)).toBeInTheDocument();
    expect(screen.getByText(/Supports Claim/i)).toBeInTheDocument();

    // Check link security
    const link = screen.getByRole('link', { name: /NASA Earth Satellite Dynamics/i });
    expect(link).toHaveAttribute('href', 'https://nasa.gov/moon-orbit');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('renders ContradictionsPanel and fusion cluster metrics', () => {
    const mockContradictions = [
      {
        contradiction_id: 'cnt-1',
        claim_id: 'c-1',
        evidence_ids: ['ev-1', 'ev-2'],
        contradiction_type: 'factual_contradiction',
        severity: 'critical' as const,
        explanation: 'Source A claims 40% growth while SEC 10-K filing reports 12% decline.',
      },
    ];

    const mockFusion = {
      supporting_evidence: 1,
      contradicting_evidence: 3,
      neutral_evidence: 0,
      total_evidence: 4,
      independent_supporting_clusters: 1,
      independent_contradicting_clusters: 2,
      support_strength: 0.25,
      contradict_strength: 0.85,
      max_support_quality: 0.6,
      max_contradict_quality: 0.95,
      duplicated_evidence_detected: 0,
      coverage: 0.9,
    };

    render(<ContradictionsPanel contradictions={mockContradictions} fusion={mockFusion} />);

    expect(screen.getByText(/CRITICAL SEVERITY/i)).toBeInTheDocument();
    expect(screen.getByText(/Source A claims 40% growth while SEC 10-K/i)).toBeInTheDocument();
    expect(screen.getByText(/Evidence Fusion & Source Independence/i)).toBeInTheDocument();
    expect(screen.getByText(/Contradicting Clusters/i)).toBeInTheDocument();
  });

  it('renders ReasoningTraceView and toggles raw JSON view', () => {
    const mockTrace = {
      claim: 'Test',
      normalized_claim: 'Test',
      claim_kind: 'factual',
      hypotheses: [],
      queries: [],
      evidence_summary: {},
      evidence: [],
      contradictions: [],
      verdict: 'VERIFIED' as Verdict,
      confidence: 1.0,
      confidence_explanation: 'Confirmed',
      reasoning: 'Confirmed',
      errors: [],
      stage_timings_ms: { retrieval: 250, contradiction: 200 },
    };

    const mockResult = {
      claim_text: 'Test',
      claim: {
        claim_id: 'claim-test',
        original_text: 'Test',
        normalized_text: 'Test',
        claim_kind: 'factual',
        entities: [],
        predicates: [],
        temporal_constraints: [],
        geographic_constraints: [],
        quantitative_constraints: [],
      },
      verdict: 'VERIFIED' as Verdict,
      confidence: 1.0,
      confidence_explanation: 'Confirmed',
    } as unknown as VerificationResult;

    render(<ReasoningTraceView trace={mockTrace} fullResult={mockResult} />);

    const header = screen.getByText(/Audit & Reasoning Trace/i);
    fireEvent.click(header);

    expect(screen.getByText(/Pipeline Stage Latency/i)).toBeInTheDocument();
    expect(screen.getByText(/250ms/i)).toBeInTheDocument();

    const rawJsonToggle = screen.getByRole('button', { name: /Show Full JSON/i });
    fireEvent.click(rawJsonToggle);

    expect(screen.getByText(/"verdict": "VERIFIED"/i)).toBeInTheDocument();
  });
});
