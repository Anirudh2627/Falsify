import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { App } from '../App';
import * as api from '../services/api';
import { StreamCallbacks, VerificationResult } from '../types/falsify';

vi.mock('../services/api');

describe('App Integration & End-to-End Workflow', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.getHealth).mockResolvedValue({
      status: 'healthy',
      app_name: 'Falsify',
      app_version: '0.1.0',
      engine_version: '0.1.0',
      retrieval_provider: 'tavily',
      llm_configured: true,
      timestamp: '2026-10-15T12:00:00Z',
    });
  });

  const mockCompletedResult: VerificationResult = {
    id: 55,
    claim_id: 'claim-55',
    claim_text: 'Global atmospheric CO2 concentration exceeded 420 ppm.',
    verdict: 'VERIFIED',
    confidence: 0.96,
    confidence_explanation: 'NOAA and Mauna Loa observatory data confirm >420 ppm.',
    confidence_breakdown: {
      evidence_quality: 0.98,
      evidence_relevance: 0.95,
      source_independence: 0.92,
      cross_source_agreement: 0.99,
      contradiction_strength: 0.02,
      temporal_validity: 0.96,
      retrieval_coverage: 0.94,
      decisiveness_margin: 0.92,
      weighted_total: 0.96,
    },
    evidence: [
      {
        evidence_id: 'ev-55',
        query_id: 'q-1',
        source_url: 'https://gml.noaa.gov/ccgg/trends/',
        title: 'NOAA Global Monitoring Laboratory',
        publisher: 'NOAA',
        domain: 'gml.noaa.gov',
        retrieved_text: 'Monthly average CO2 levels reached 422.8 ppm in May 2024.',
        relevant_passages: ['Monthly average CO2 levels reached 422.8 ppm in May 2024.'],
      },
    ],
    hypotheses: [
      {
        hypothesis_id: 'h-1',
        hypothesis: 'CO2 concentration is below 420 ppm in recent measurements',
        category: 'numerical_bound',
        priority: 1,
        tested: true,
        queries_run: 2,
        evidence_found: 1,
        outcome: 'falsified',
      },
    ],
    contradictions: [],
    generated_queries: [
      {
        query_id: 'q-1',
        query: 'Mauna Loa CO2 levels 2024 ppm',
        hypothesis: 'CO2 concentration is below 420 ppm',
        purpose: 'Check official atmospheric sensor readings',
        query_type: 'adversarial',
        results_found: 5,
      },
    ],
    assessments: [
      {
        evidence_id: 'ev-55',
        supports_claim: true,
        contradicts_claim: false,
        stance: 'supporting',
        relevance_score: 0.95,
        source_quality_score: 0.98,
        source_tier: 1,
        temporal_validity: 0.96,
        is_direct: true,
        reasoning: 'Direct observatory measurement',
      },
    ],
    fusion_output: null,
    reasoning_trace: {
      stages: [{ stage: 'retrieval', duration_ms: 120, status: 'completed' }],
      total_duration_ms: 350,
      stage_timings_ms: { retrieval: 120, reasoning: 230 },
    },
  };

  it('executes full verification stream lifecycle from input to completed dashboard', async () => {
    vi.mocked(api.streamVerification).mockImplementation(
      async (claim: string, callbacks: StreamCallbacks) => {
        callbacks.onStarted?.({
          message: 'Adversarial verification started',
          claim,
        });

        callbacks.onProgress?.({
          stage: 'retrieval',
          message: 'Executing multi-source queries',
          progress: 0.4,
        });

        callbacks.onCompleted?.({
          verification_id: 55,
          verdict: 'VERIFIED',
          confidence: 0.96,
          result: mockCompletedResult,
        });
      }
    );

    render(<App />);

    // Check navbar and brand
    expect(screen.getByText('Falsify')).toBeInTheDocument();
    expect(screen.getByText(/Research Engine/i)).toBeInTheDocument();

    // Type claim
    const textarea = screen.getByLabelText(/Claim statement to verify/i);
    fireEvent.change(textarea, { target: { value: 'Global atmospheric CO2 concentration exceeded 420 ppm.' } });

    // Click verify
    const verifyBtn = screen.getByRole('button', { name: /Verify Claim/i });
    fireEvent.click(verifyBtn);

    // Verify streamVerification was called exactly once
    expect(api.streamVerification).toHaveBeenCalledTimes(1);
    expect(api.streamVerification).toHaveBeenCalledWith(
      'Global atmospheric CO2 concentration exceeded 420 ppm.',
      expect.any(Object),
      expect.any(Object)
    );

    // Completed result dashboard should be visible
    await waitFor(() => {
      expect(screen.getByText('VERIFIED')).toBeInTheDocument();
      expect(screen.getAllByText(/96%/i).length).toBeGreaterThan(0);
      expect(screen.getByText(/NOAA Global Monitoring Laboratory/i)).toBeInTheDocument();
      expect(screen.getByText(/Monthly average CO2 levels reached 422.8 ppm/i)).toBeInTheDocument();
    });

    // Reset button returns to verification form
    const newBtn = screen.getByRole('button', { name: /New Verification/i });
    fireEvent.click(newBtn);

    expect(screen.getByLabelText(/Claim statement to verify/i)).toBeInTheDocument();
  });

  it('renders safe error alert when stream reports verification_error', async () => {
    vi.mocked(api.streamVerification).mockImplementation(
      async (_claim: string, callbacks: StreamCallbacks) => {
        callbacks.onError?.({
          code: 'RateLimitError',
          message: 'Search API rate limit exceeded. Please retry later.',
        });
      }
    );

    render(<App />);

    const textarea = screen.getByLabelText(/Claim statement to verify/i);
    fireEvent.change(textarea, { target: { value: 'Test error claim' } });

    const verifyBtn = screen.getByRole('button', { name: /Verify Claim/i });
    fireEvent.click(verifyBtn);

    await waitFor(() => {
      expect(screen.getByText(/Search API rate limit exceeded/i)).toBeInTheDocument();
    });

    // Result dashboard must NOT be displayed
    expect(screen.queryByText('VERIFIED')).not.toBeInTheDocument();
  });

  it('renders interrupted connection error when stream closes prematurely', async () => {
    vi.mocked(api.streamVerification).mockRejectedValueOnce(
      new Error('The verification stream closed prematurely before completion.')
    );

    render(<App />);

    const textarea = screen.getByLabelText(/Claim statement to verify/i);
    fireEvent.change(textarea, { target: { value: 'Interrupted stream claim' } });

    fireEvent.click(screen.getByRole('button', { name: /Verify Claim/i }));

    await waitFor(() => {
      expect(screen.getByText(/stream closed prematurely/i)).toBeInTheDocument();
    });

    // Result dashboard must NOT be displayed
    expect(screen.queryByText('VERIFIED')).not.toBeInTheDocument();
  });

  it('allows navigation between Verification and History views', async () => {
    vi.mocked(api.getVerifications).mockResolvedValueOnce({
      items: [],
      total: 0,
      page: 1,
      page_size: 10,
      total_pages: 0,
    });

    render(<App />);

    // Click History tab in Navbar
    const historyTab = screen.getByRole('button', { name: /History/i });
    fireEvent.click(historyTab);

    expect(await screen.findByText(/Verification History/i)).toBeInTheDocument();

    // Click Verification tab
    const verifyTab = screen.getByRole('button', { name: /^Verification$/i });
    fireEvent.click(verifyTab);

    expect(screen.getByLabelText(/Claim statement to verify/i)).toBeInTheDocument();
  });
});
