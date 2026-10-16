import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { App } from '../App';
import * as api from '../services/api';
import { StreamCallbacks, VerificationResult, PaginatedVerificationHistory } from '../types/falsify';

vi.mock('../services/api');

describe('Phase 5 Frontend End-to-End Workflow & Reliability Hardening', () => {
  const mockResultRefuted: VerificationResult = {
    id: 99,
    claim_id: 'claim-99',
    claim_text: 'Company X reported 40% revenue growth in fiscal 2025.',
    verdict: 'REFUTED',
    confidence: 0.88,
    confidence_explanation: 'Official SEC 10-K filing reports 12% revenue decline.',
    confidence_breakdown: {
      evidence_quality: 0.95,
      evidence_relevance: 0.92,
      source_independence: 0.90,
      cross_source_agreement: 0.96,
      contradiction_strength: 0.94,
      temporal_validity: 0.90,
      retrieval_coverage: 0.88,
      decisiveness_margin: 0.85,
      weighted_total: 0.88,
    },
    evidence: [
      {
        evidence_id: 'ev-99-1',
        query_id: 'q-99-1',
        source_url: 'https://sec.gov/edgar/data/companyx-10k.htm',
        title: 'Company X Form 10-K Annual Report',
        publisher: 'U.S. Securities and Exchange Commission',
        domain: 'sec.gov',
        retrieved_text: 'Total revenue for fiscal year 2025 declined 12.4% year-over-year to $1.2B.',
        relevant_passages: ['Total revenue for fiscal year 2025 declined 12.4% year-over-year to $1.2B.'],
      },
    ],
    hypotheses: [
      {
        hypothesis_id: 'h-99-1',
        hypothesis: 'Official audited filings report lower or negative growth',
        category: 'contradictory_metric',
        priority: 1,
        tested: true,
        queries_run: 2,
        evidence_found: 1,
        outcome: 'falsified',
      },
    ],
    queries: [
      {
        query_id: 'q-99-1',
        query: 'Company X 2025 10-K total revenue',
        hypothesis: 'Official audited filings report lower or negative growth',
        purpose: 'Retrieve verified SEC financial statements',
        query_type: 'primary_source',
        results_found: 1,
      },
    ],
    assessments: [
      {
        evidence_id: 'ev-99-1',
        supports_claim: false,
        contradicts_claim: true,
        stance: 'contradicting',
        relevance_score: 0.99,
        source_quality_score: 0.98,
        source_tier: 1,
        temporal_validity: 0.95,
        is_direct: true,
        reasoning: 'Direct SEC audited report provides certified negative revenue delta.',
      },
    ],
    contradictions: [
      {
        contradiction_id: 'cnt-99-1',
        claim_id: 'claim-99',
        evidence_ids: ['ev-99-1'],
        contradiction_type: 'numerical_discrepancy',
        severity: 'critical',
        explanation: 'Claim asserts 40% growth whereas audited 10-K documents 12.4% decline.',
      },
    ],
    fusion: {
      supporting_evidence: 0,
      contradicting_evidence: 1,
      neutral_evidence: 0,
      total_evidence: 1,
      independent_supporting_clusters: 0,
      independent_contradicting_clusters: 1,
      support_strength: 0.0,
      contradict_strength: 0.95,
      max_support_quality: 0.0,
      max_contradict_quality: 0.98,
      duplicated_evidence_detected: 0,
      coverage: 0.9,
    },
    reasoning_trace: {
      stages: [{ stage: 'retrieval', duration_ms: 150, status: 'completed' }],
      total_duration_ms: 320,
      stage_timings_ms: { normalization: 20, retrieval: 150, evaluation: 150 },
    },
  };

  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.getHealth).mockResolvedValue({
      status: 'ok',
      app_name: 'Falsify API',
      app_version: '1.0.0',
      engine_version: '1.0.0',
      retrieval_provider: 'tavily',
      llm_configured: true,
      timestamp: '2026-10-15T12:00:00Z',
    });
  });

  it('executes full 13-step workflow: stream verification, view in history, open detail, delete record', async () => {
    // History mock state
    let historyItems = [
      {
        id: 99,
        claim_id: 'claim-99',
        claim_text: 'Company X reported 40% revenue growth in fiscal 2025.',
        verdict: 'REFUTED' as const,
        confidence: 0.88,
        created_at: '2026-10-15T12:00:00Z',
      },
    ];

    vi.mocked(api.getVerifications).mockImplementation(async () => {
      return {
        items: historyItems,
        total: historyItems.length,
        page: 1,
        page_size: 10,
        total_pages: 1,
      } as PaginatedVerificationHistory;
    });

    vi.mocked(api.getVerificationById).mockResolvedValue(mockResultRefuted);
    vi.mocked(api.deleteVerification).mockImplementation(async (id: number) => {
      historyItems = historyItems.filter((item) => item.id !== id);
    });

    vi.mocked(api.streamVerification).mockImplementation(
      async (claim: string, callbacks: StreamCallbacks) => {
        // Step 4: Started event
        callbacks.onStarted?.({
          message: 'Adversarial verification started',
          claim,
        });

        // Step 5: Progress event
        callbacks.onProgress?.({
          stage: 'retrieval',
          message: 'Searching for official filings and financial reports',
          progress: 0.45,
        });

        // Step 6: Completed event with actual full result
        callbacks.onCompleted?.({
          verification_id: 99,
          verdict: 'REFUTED',
          confidence: 0.88,
          result: mockResultRefuted,
        });
      }
    );

    render(<App />);

    // Step 1: Open frontend - verify brand
    expect(screen.getByText('Falsify')).toBeInTheDocument();

    // Step 2: Enter valid claim
    const textarea = screen.getByLabelText(/Claim statement to verify/i);
    fireEvent.change(textarea, {
      target: { value: 'Company X reported 40% revenue growth in fiscal 2025.' },
    });

    // Step 3: Submit claim exactly once
    const verifyBtn = screen.getByRole('button', { name: /Verify Claim/i });
    fireEvent.click(verifyBtn);

    expect(api.streamVerification).toHaveBeenCalledTimes(1);

    // Step 6 & 7: Verify completed result dashboard is rendered
    await waitFor(() => {
      expect(screen.getByText('REFUTED')).toBeInTheDocument();
      expect(screen.getAllByText(/88%/i).length).toBeGreaterThan(0);
      expect(screen.getByText(/Company X Form 10-K Annual Report/i)).toBeInTheDocument();
      expect(screen.getByText(/Claim asserts 40% growth whereas audited 10-K/i)).toBeInTheDocument();
    });

    // Step 8: Open history page
    const historyNavBtn = screen.getByRole('button', { name: /History/i });
    fireEvent.click(historyNavBtn);

    // Step 9: Locate newly created record
    expect(await screen.findByText(/Company X reported 40% revenue growth in fiscal 2025/i)).toBeInTheDocument();
    expect(screen.getAllByText('REFUTED').length).toBeGreaterThan(0);

    // Step 10: Open its details
    const viewDetailBtn = screen.getByRole('button', { name: /View detail for verification 99/i });
    fireEvent.click(viewDetailBtn);

    // Step 11: Verify stored result matches original result without rerunning verification
    await waitFor(() => {
      expect(api.getVerificationById).toHaveBeenCalledWith(99);
      expect(screen.getByText('REFUTED')).toBeInTheDocument();
      expect(screen.getByText(/Viewing Persisted Verification Record #99/i)).toBeInTheDocument();
      expect(screen.getByText(/Company X Form 10-K Annual Report/i)).toBeInTheDocument();
    });

    // Engine stream must not have been invoked again
    expect(api.streamVerification).toHaveBeenCalledTimes(1);

    // Return to history and delete record
    const returnBtn = screen.getByRole('button', { name: /Return to History/i });
    fireEvent.click(returnBtn);

    // Step 12: Delete record
    const deleteBtn = await screen.findByRole('button', { name: /Delete verification 99/i });
    fireEvent.click(deleteBtn);

    // Confirmation dialog
    expect(screen.getByRole('heading', { name: /Delete Verification Record\?/i })).toBeInTheDocument();
    const confirmDeleteBtn = screen.getByRole('button', { name: /Delete Record/i });
    fireEvent.click(confirmDeleteBtn);

    // Step 13: Verify record no longer appears in history
    await waitFor(() => {
      expect(api.deleteVerification).toHaveBeenCalledWith(99);
      expect(screen.getByText(/No verification records found/i)).toBeInTheDocument();
    });
  });

  it('recovers cleanly and allows retry when verification stream fails with an error', async () => {
    // 1st attempt: fails
    vi.mocked(api.streamVerification).mockImplementationOnce(
      async (_claim: string, callbacks: StreamCallbacks) => {
        callbacks.onError?.({
          code: 'RateLimitError',
          message: 'Tavily API rate limit exceeded.',
        });
      }
    );

    render(<App />);

    const textarea = screen.getByLabelText(/Claim statement to verify/i);
    fireEvent.change(textarea, { target: { value: 'First failing claim' } });

    fireEvent.click(screen.getByRole('button', { name: /Verify Claim/i }));

    // Error alert is rendered
    await waitFor(() => {
      expect(screen.getByText(/Tavily API rate limit exceeded/i)).toBeInTheDocument();
    });

    // Result dashboard must NOT be displayed
    expect(screen.queryByText('VERIFIED')).not.toBeInTheDocument();
    expect(screen.queryByText('REFUTED')).not.toBeInTheDocument();

    // 2nd attempt: succeeds
    vi.mocked(api.streamVerification).mockImplementationOnce(
      async (_claim: string, callbacks: StreamCallbacks) => {
        callbacks.onCompleted?.({
          verification_id: 100,
          verdict: 'VERIFIED',
          confidence: 0.99,
          result: {
            ...mockResultRefuted,
            id: 100,
            verdict: 'VERIFIED',
            confidence: 0.99,
          },
        });
      }
    );

    fireEvent.change(textarea, { target: { value: 'Second successful retry claim' } });
    fireEvent.click(screen.getByRole('button', { name: /Verify Claim/i }));

    await waitFor(() => {
      expect(screen.getByText('VERIFIED')).toBeInTheDocument();
      expect(screen.queryByText(/Tavily API rate limit exceeded/i)).not.toBeInTheDocument();
    });
  });

  it('handles client cancellation without displaying a success state', async () => {
    let cancelCalled = false;
    vi.mocked(api.streamVerification).mockImplementation(
      async (_claim: string, callbacks: StreamCallbacks, signal?: AbortSignal) => {
        callbacks.onStarted?.({ message: 'Starting...', claim: 'Cancel claim' });
        // Wait until aborted
        while (!signal?.aborted) {
          await new Promise((resolve) => setTimeout(resolve, 50));
        }
        cancelCalled = true;
        const abortErr = new Error('The user aborted a request.');
        abortErr.name = 'AbortError';
        throw abortErr;
      }
    );

    render(<App />);

    const textarea = screen.getByLabelText(/Claim statement to verify/i);
    fireEvent.change(textarea, { target: { value: 'Cancel claim' } });
    fireEvent.click(screen.getByRole('button', { name: /Verify Claim/i }));

    // Click cancel stream button
    const cancelBtn = await screen.findByRole('button', { name: /Cancel Stream/i });
    fireEvent.click(cancelBtn);

    await waitFor(() => {
      expect(screen.getByText(/stream was cancelled by user/i)).toBeInTheDocument();
    });

    expect(screen.queryByText('VERIFIED')).not.toBeInTheDocument();
    expect(screen.queryByText('REFUTED')).not.toBeInTheDocument();
  });

  it('renders untrusted claim and evidence text safely without script injection (XSS defense)', async () => {
    const xssResult: VerificationResult = {
      id: 777,
      claim_id: 'xss-claim',
      claim_text: '<script>alert("xss")</script><img src=x onerror=alert(1)>',
      verdict: 'REFUTED',
      confidence: 0.75,
      confidence_explanation: '<svg onload=alert("expl")>',
      evidence: [
        {
          evidence_id: 'ev-xss',
          source_url: 'https://example.com/exploit',
          title: '<iframe src="javascript:alert(1)"></iframe>Malicious Title',
          publisher: 'Unknown',
          domain: 'example.com',
          retrieved_text: '<script>window.pwned=true</script>Evidence snippet',
          relevant_passages: ['<script>window.pwned=true</script>Evidence snippet'],
        },
      ],
      hypotheses: [],
      queries: [],
      assessments: [],
      contradictions: [],
      fusion: null as any,
      reasoning_trace: { stages: [], total_duration_ms: 100, stage_timings_ms: {} },
    };

    vi.mocked(api.streamVerification).mockImplementation(
      async (_claim: string, callbacks: StreamCallbacks) => {
        callbacks.onCompleted?.({
          verification_id: 777,
          verdict: 'REFUTED',
          confidence: 0.75,
          result: xssResult,
        });
      }
    );

    render(<App />);

    const textarea = screen.getByLabelText(/Claim statement to verify/i);
    fireEvent.change(textarea, { target: { value: '<script>alert("xss")</script>' } });
    fireEvent.click(screen.getByRole('button', { name: /Verify Claim/i }));

    await waitFor(() => {
      expect(screen.getAllByText('REFUTED').length).toBeGreaterThan(0);
      // Ensure scripts are rendered as text content, not executable script tags
      expect(document.querySelector('script[src="javascript:alert(1)"]')).toBeNull();
      expect(screen.getAllByText(/<script>alert\("xss"\)<\/script>/i).length).toBeGreaterThan(0);
      expect(screen.getByText(/<iframe src="javascript:alert\(1\)">/i)).toBeInTheDocument();
    });
  });
});
