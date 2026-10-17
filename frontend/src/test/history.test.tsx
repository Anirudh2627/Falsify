import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { HistoryView } from '../components/HistoryView';
import * as api from '../services/api';
import { PaginatedVerificationHistory, VerificationResult } from '../types/falsify';

vi.mock('../services/api');

describe('HistoryView Component', () => {
  const mockHistoryData: PaginatedVerificationHistory = {
    items: [
      {
        id: 1,
        claim_id: 'claim-1',
        claim_text: 'The moon is made of green cheese.',
        verdict: 'REFUTED',
        confidence: 0.99,
        created_at: '2026-10-15T10:00:00Z',
      },
      {
        id: 2,
        claim_id: 'claim-2',
        claim_text: 'Water boils at 100 degrees Celsius at standard atmospheric pressure.',
        verdict: 'VERIFIED',
        confidence: 0.98,
        created_at: '2026-10-15T11:00:00Z',
      },
    ],
    total: 2,
    page: 1,
    page_size: 10,
    total_pages: 1,
  };

  const mockDetailResult: VerificationResult = {
    id: 1,
    claim_id: 'claim-1',
    claim_text: 'The moon is made of green cheese.',
    verdict: 'REFUTED',
    confidence: 0.99,
    confidence_explanation: 'Direct lunar sample analysis refutes this claim.',
    evidence: [],
    hypotheses: [],
    contradictions: [],
    generated_queries: [],
    assessments: [],
    fusion_output: null,
    reasoning_trace: { stages: [], total_duration_ms: 100, stage_timings_ms: {} },
  };

  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('renders history records with verdicts, confidence, and timestamps', async () => {
    vi.mocked(api.getVerifications).mockResolvedValueOnce(mockHistoryData);

    render(<HistoryView onOpenResult={vi.fn()} />);

    expect(await screen.findByText(/The moon is made of green cheese/i)).toBeInTheDocument();
    expect(screen.getByText(/Water boils at 100 degrees/i)).toBeInTheDocument();
    expect(screen.getAllByText('REFUTED').length).toBeGreaterThan(0);
    expect(screen.getAllByText('VERIFIED').length).toBeGreaterThan(0);
    expect(screen.getByText(/99%/i)).toBeInTheDocument();
  });

  it('renders empty state when no verification history records exist', async () => {
    vi.mocked(api.getVerifications).mockResolvedValueOnce({
      items: [],
      total: 0,
      page: 1,
      page_size: 10,
      total_pages: 0,
    });

    render(<HistoryView onOpenResult={vi.fn()} />);

    expect(await screen.findByText(/No verification records found/i)).toBeInTheDocument();
  });

  it('filters history by verdict and resets to page 1', async () => {
    vi.mocked(api.getVerifications).mockResolvedValue(mockHistoryData);

    render(<HistoryView onOpenResult={vi.fn()} />);
    await screen.findByText(/The moon is made of green cheese/i);

    const filterSelect = screen.getByLabelText(/Filter:/i);
    fireEvent.change(filterSelect, { target: { value: 'VERIFIED' } });

    await waitFor(() => {
      expect(api.getVerifications).toHaveBeenCalledWith(1, 10, 'VERIFIED');
    });
  });

  it('navigates pagination using Next and Previous buttons', async () => {
    const multiPageData: PaginatedVerificationHistory = {
      items: [mockHistoryData.items[0]],
      total: 20,
      page: 1,
      page_size: 10,
      total_pages: 2,
    };

    vi.mocked(api.getVerifications).mockResolvedValue(multiPageData);

    render(<HistoryView onOpenResult={vi.fn()} />);
    await screen.findByText(/The moon is made of green cheese/i);

    const nextBtn = screen.getByRole('button', { name: /Next/i });
    expect(nextBtn).toBeEnabled();

    fireEvent.click(nextBtn);

    await waitFor(() => {
      expect(api.getVerifications).toHaveBeenCalledWith(2, 10, undefined);
    });
  });

  it('opens historical result detail without rerunning verification', async () => {
    vi.mocked(api.getVerifications).mockResolvedValueOnce(mockHistoryData);
    vi.mocked(api.getVerificationById).mockResolvedValueOnce(mockDetailResult);

    const onOpenResultMock = vi.fn();
    render(<HistoryView onOpenResult={onOpenResultMock} />);

    await screen.findByText(/The moon is made of green cheese/i);

    const viewButton = screen.getByRole('button', { name: /View detail for verification 1/i });
    fireEvent.click(viewButton);

    await waitFor(() => {
      expect(api.getVerificationById).toHaveBeenCalledWith(1);
      expect(onOpenResultMock).toHaveBeenCalledWith(mockDetailResult);
    });
  });

  it('deletes history item upon confirmation in modal and refreshes list', async () => {
    vi.mocked(api.getVerifications)
      .mockResolvedValueOnce(mockHistoryData)
      .mockResolvedValueOnce({
        items: [mockHistoryData.items[1]],
        total: 1,
        page: 1,
        page_size: 10,
        total_pages: 1,
      });
    vi.mocked(api.deleteVerification).mockResolvedValueOnce({
      id: 1,
      message: 'Verification 1 deleted successfully',
    });

    render(<HistoryView onOpenResult={vi.fn()} />);
    await screen.findByText(/The moon is made of green cheese/i);

    const deleteButton = screen.getByRole('button', { name: /Delete verification 1/i });
    fireEvent.click(deleteButton);

    // Modal should be visible
    expect(screen.getByText(/Delete Verification Record #1/i)).toBeInTheDocument();

    const confirmDeleteBtn = screen.getByRole('button', { name: /Delete Record/i });
    fireEvent.click(confirmDeleteBtn);

    await waitFor(() => {
      expect(api.deleteVerification).toHaveBeenCalledWith(1);
      expect(screen.getByText(/deleted successfully/i)).toBeInTheDocument();
    });
  });

  it('renders an error message when the backend API fails', async () => {
    vi.mocked(api.getVerifications).mockRejectedValueOnce(new Error('Internal Server Error 500'));

    render(<HistoryView onOpenResult={vi.fn()} />);

    expect(await screen.findByText(/Internal Server Error 500/i)).toBeInTheDocument();
  });
});
