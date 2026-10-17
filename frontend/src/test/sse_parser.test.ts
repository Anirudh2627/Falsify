import { describe, it, expect, vi } from 'vitest';
import { parseSSEStream, streamVerification } from '../services/api';
import { StreamProgressEvent, VerificationResult } from '../types/falsify';

function createMockStream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let index = 0;
  return new ReadableStream({
    pull(controller) {
      if (index < chunks.length) {
        controller.enqueue(encoder.encode(chunks[index]));
        index++;
      } else {
        controller.close();
      }
    },
  });
}

describe('SSE Stream Parser', () => {
  it('parses multiple SSE events in a single chunk', async () => {
    const chunk = [
      'event: verification_started\n',
      'data: {"event": "verification_started", "message": "Starting verification"}\n\n',
      'event: verification_progress\n',
      'data: {"event": "verification_progress", "stage": "retrieval", "progress": 0.5, "message": "Searching evidence"}\n\n',
    ].join('');

    const stream = createMockStream([chunk]);
    const startedSpy = vi.fn();
    const progressSpy = vi.fn();

    await parseSSEStream(stream, {
      onStarted: startedSpy,
      onProgress: progressSpy,
    });

    expect(startedSpy).toHaveBeenCalledTimes(1);
    expect(startedSpy).toHaveBeenCalledWith(
      expect.objectContaining({ event: 'verification_started', message: 'Starting verification' })
    );
    expect(progressSpy).toHaveBeenCalledTimes(1);
    expect(progressSpy).toHaveBeenCalledWith(
      expect.objectContaining({ event: 'verification_progress', stage: 'retrieval', progress: 0.5 })
    );
  });

  it('correctly handles events split across chunk boundaries', async () => {
    const chunk1 = 'event: verification_prog';
    const chunk2 = 'ress\ndata: {"event": "verification_progress", "stage": "adversarial_hyp';
    const chunk3 = 'otheses", "progress": 0.35, "message": "Generating hypotheses"}\n\n';

    const stream = createMockStream([chunk1, chunk2, chunk3]);
    const progressSpy = vi.fn();

    await parseSSEStream(stream, {
      onProgress: progressSpy,
    });

    expect(progressSpy).toHaveBeenCalledTimes(1);
    expect(progressSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        event: 'verification_progress',
        stage: 'adversarial_hypotheses',
        progress: 0.35,
        message: 'Generating hypotheses',
      })
    );
  });

  it('supports both CRLF and LF frame separators', async () => {
    const crlfChunk = 'event: verification_started\r\ndata: {"event": "verification_started", "message": "CRLF started"}\r\n\r\n';
    const lfChunk = 'event: verification_progress\ndata: {"event": "verification_progress", "stage": "eval", "progress": 0.8, "message": "LF stage"}\n\n';

    const stream = createMockStream([crlfChunk, lfChunk]);
    const startedSpy = vi.fn();
    const progressSpy = vi.fn();

    await parseSSEStream(stream, {
      onStarted: startedSpy,
      onProgress: progressSpy,
    });

    expect(startedSpy).toHaveBeenCalledTimes(1);
    expect(startedSpy).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'CRLF started' })
    );
    expect(progressSpy).toHaveBeenCalledTimes(1);
    expect(progressSpy).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'LF stage' })
    );
  });

  it('correctly handles UTF-8 multibyte characters split across chunks', async () => {
    // "Café verification — 100%"
    // é in UTF-8 is 0xC3 0xA9
    const str1 = 'event: verification_progress\ndata: {"event": "verification_progress", "stage": "test", "progress": 0.5, "message": "Caf';
    const str2 = 'é verify"}\n\n';

    const encoder = new TextEncoder();
    const bytes1 = encoder.encode(str1);
    const bytes2 = encoder.encode(str2);

    let index = 0;
    const stream = new ReadableStream<Uint8Array>({
      pull(controller) {
        if (index === 0) {
          controller.enqueue(bytes1);
          index++;
        } else if (index === 1) {
          controller.enqueue(bytes2);
          index++;
        } else {
          controller.close();
        }
      },
    });

    const progressSpy = vi.fn();
    await parseSSEStream(stream, { onProgress: progressSpy });

    expect(progressSpy).toHaveBeenCalledTimes(1);
    expect(progressSpy).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'Café verify' })
    );
  });

  it('safely tolerates malformed JSON frames without crashing entire parser', async () => {
    const badChunk = 'event: verification_progress\ndata: {MALFORMED_JSON}\n\n';
    const goodChunk = 'event: verification_progress\ndata: {"event": "verification_progress", "stage": "done", "progress": 1.0, "message": "Recovered"}\n\n';

    const stream = createMockStream([badChunk, goodChunk]);
    const progressSpy = vi.fn();

    await parseSSEStream(stream, { onProgress: progressSpy });

    // The good chunk should still be parsed
    expect(progressSpy).toHaveBeenCalledTimes(1);
    expect(progressSpy).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'Recovered' })
    );
  });

  it('calls onCompleted with full VerificationResult payload', async () => {
    const mockResult: VerificationResult = {
      claim_id: 'claim_123',
      claim_text: 'Test claim',
      verdict: 'VERIFIED',
      confidence: 0.95,
      confidence_explanation: 'Strong factual agreement',
      confidence_breakdown: {
        evidence_quality: 0.9,
        evidence_relevance: 0.9,
        source_independence: 0.8,
        cross_source_agreement: 1.0,
        contradiction_strength: 1.0,
        temporal_validity: 1.0,
        retrieval_coverage: 1.0,
        decisiveness_margin: 0.5,
        weighted_total: 0.95,
      },
      claim: {
        claim_id: 'claim_123',
        original_text: 'Test claim',
        normalized_text: 'Test claim',
        claim_kind: 'factual',
        entities: [],
        predicates: [],
        temporal_constraints: [],
        geographic_constraints: [],
        quantitative_constraints: [],
      },
      hypotheses: [],
      queries: [],
      generated_queries: [],
      evidence: [],
      assessments: [],
      contradictions: [],
      fusion: {
        supporting_evidence: 0,
        contradicting_evidence: 0,
        neutral_evidence: 0,
        total_evidence: 0,
        independent_supporting_clusters: 0,
        independent_contradicting_clusters: 0,
        support_strength: 0,
        contradict_strength: 0,
        max_support_quality: 0,
        max_contradict_quality: 0,
        duplicated_evidence_detected: 0,
        coverage: 0,
      },
      reasoning_trace: {
        claim: 'Test claim',
        normalized_claim: 'Test claim',
        claim_kind: 'factual',
        hypotheses: [],
        queries: [],
        evidence_summary: {},
        evidence: [],
        contradictions: [],
        verdict: 'VERIFIED',
        confidence: 0.95,
        confidence_explanation: 'Strong factual agreement',
        reasoning: 'Test reasoning trace',
        errors: [],
        stage_timings_ms: { retrieval: 100, analysis: 20 },
      },
      errors: [],
      verification_id: 42,
    };

    const chunk = `event: verification_completed\ndata: ${JSON.stringify({
      event: 'verification_completed',
      verification_id: 42,
      result: mockResult,
    })}\n\n`;

    const stream = createMockStream([chunk]);
    const completedSpy = vi.fn();

    await parseSSEStream(stream, { onCompleted: completedSpy });

    expect(completedSpy).toHaveBeenCalledTimes(1);
    expect(completedSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        verification_id: 42,
        result: expect.objectContaining({ verdict: 'VERIFIED', confidence: 0.95 }),
      })
    );
  });

  it('calls onError when a verification_error event is received', async () => {
    const chunk = 'event: verification_error\ndata: {"event": "verification_error", "error": "LLM rate limit reached"}\n\n';
    const stream = createMockStream([chunk]);
    const errorSpy = vi.fn();

    await parseSSEStream(stream, { onError: errorSpy });

    expect(errorSpy).toHaveBeenCalledTimes(1);
    expect(errorSpy).toHaveBeenCalledWith(
      expect.objectContaining({ error: 'LLM rate limit reached' })
    );
  });

  it('calls onError if stream terminates prematurely without completion or error event', async () => {
    const partialStream = createMockStream([
      'event: verification_started\ndata: {"event": "verification_started", "message": "Start"}\n\n',
      'event: verification_progress\ndata: {"event": "verification_progress", "stage": "retrieval", "progress": 0.2, "message": "Searching"}\n\n',
    ]);

    const errorSpy = vi.fn();
    await parseSSEStream(partialStream, { onError: errorSpy });

    expect(errorSpy).toHaveBeenCalledWith(
      expect.objectContaining({ code: 'StreamInterrupted' })
    );
  });
});

