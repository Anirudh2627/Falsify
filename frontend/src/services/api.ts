/**
 * API client layer for Falsify backend services.
 */

import {
  HealthResponse,
  PaginatedVerificationHistory,
  StreamCompletedEvent,
  StreamErrorEvent,
  StreamProgressEvent,
  StreamStartedEvent,
  VerificationResult,
} from '../types/falsify';

const BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

export interface StreamCallbacks {
  onStarted?: (event: StreamStartedEvent) => void;
  onProgress?: (event: StreamProgressEvent) => void;
  onCompleted?: (event: StreamCompletedEvent) => void;
  onError?: (event: StreamErrorEvent) => void;
}

/**
 * Standard synchronous verification request.
 */
export async function verifyClaim(claim: string): Promise<VerificationResult> {
  const response = await fetch(`${BASE_URL}/api/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ claim }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    const detail = errorData?.detail || `Verification failed (HTTP ${response.status})`;
    throw new Error(detail);
  }

  return response.json();
}

/**
 * Real-time SSE streaming verification using fetch() with a ReadableStream.
 * Handles chunk boundaries, CRLF/LF line endings, multi-event chunks, and clean stream termination.
 */
export async function streamVerification(
  claim: string,
  callbacks: StreamCallbacks,
  signal?: AbortSignal
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}/api/verify/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify({ claim }),
      signal,
    });
  } catch (err: unknown) {
    if (signal?.aborted) {
      return;
    }
    const message = err instanceof Error ? err.message : 'Network connection failed';
    callbacks.onError?.({ code: 'NetworkError', message });
    return;
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    const detail = errorData?.detail || `Streaming request failed (HTTP ${response.status})`;
    callbacks.onError?.({ code: `HTTP_${response.status}`, message: detail });
    return;
  }

  if (!response.body) {
    callbacks.onError?.({
      code: 'StreamError',
      message: 'Server returned empty response body',
    });
    return;
  }

  await parseSSEStream(response.body, callbacks, signal);
}

/**
 * Parses an SSE ReadableStream, handling chunk boundaries, CRLF/LF line endings,
 * multi-event chunks, and UTF-8 multi-byte decoding across chunks.
 */
export async function parseSSEStream(
  stream: ReadableStream<Uint8Array>,
  callbacks: StreamCallbacks,
  signal?: AbortSignal
): Promise<void> {
  const reader = stream.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';
  let completedOrErrorReceived = false;

  const parseFrame = (frame: string) => {
    let eventName = '';
    let dataStr = '';

    const lines = frame.split('\n');
    for (const rawLine of lines) {
      const line = rawLine.trim();
      if (line.startsWith('event:')) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith('data:')) {
        dataStr = line.slice(5).trim();
      }
    }

    if (!eventName || !dataStr) return;

    try {
      const data = JSON.parse(dataStr);
      switch (eventName) {
        case 'verification_started':
          callbacks.onStarted?.(data);
          break;
        case 'verification_progress':
          callbacks.onProgress?.(data);
          break;
        case 'verification_completed':
          completedOrErrorReceived = true;
          callbacks.onCompleted?.(data);
          break;
        case 'verification_error':
          completedOrErrorReceived = true;
          callbacks.onError?.(data);
          break;
        default:
          console.warn(`[Falsify SSE] Unknown event received: ${eventName}`, data);
      }
    } catch (parseErr) {
      console.error('[Falsify SSE] Failed to parse event payload JSON:', dataStr, parseErr);
    }
  };

  try {
    while (true) {
      const { done, value } = await reader.read();

      if (value) {
        buffer += decoder.decode(value, { stream: true });
        // Normalize CRLF to LF
        buffer = buffer.replace(/\r\n/g, '\n');

        // Extract complete frames delimited by double newline
        let boundaryIndex = buffer.indexOf('\n\n');
        while (boundaryIndex !== -1) {
          const frame = buffer.slice(0, boundaryIndex).trim();
          buffer = buffer.slice(boundaryIndex + 2);
          if (frame) {
            parseFrame(frame);
          }
          boundaryIndex = buffer.indexOf('\n\n');
        }
      }

      if (done) {
        // Flush remaining buffer
        buffer += decoder.decode();
        buffer = buffer.replace(/\r\n/g, '\n').trim();
        if (buffer) {
          parseFrame(buffer);
        }
        break;
      }
    }

    // Guard: if stream terminated prematurely without completion or error event
    if (!completedOrErrorReceived && !signal?.aborted) {
      callbacks.onError?.({
        code: 'StreamInterrupted',
        message: 'The verification stream closed prematurely before completion.',
      });
    }
  } catch (err: unknown) {
    if (signal?.aborted) {
      return;
    }
    const message = err instanceof Error ? err.message : 'Stream processing encountered an error';
    callbacks.onError?.({ code: 'StreamReadError', message });
    throw err;
  } finally {
    try {
      reader.releaseLock();
    } catch {
      // Ignore reader cleanup errors
    }
  }
}


/**
 * Fetch paginated history with optional verdict filter.
 */
export async function getVerifications(
  page = 1,
  pageSize = 10,
  verdict?: string
): Promise<PaginatedVerificationHistory> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (verdict) {
    params.set('verdict', verdict);
  }

  const response = await fetch(`${BASE_URL}/api/verifications?${params.toString()}`);
  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    throw new Error(errorData?.detail || `Failed to fetch history (HTTP ${response.status})`);
  }
  return response.json();
}

/**
 * Fetch complete historical verification result by ID.
 */
export async function getVerificationById(id: number): Promise<VerificationResult> {
  const response = await fetch(`${BASE_URL}/api/verifications/${id}`);
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error(`Verification record #${id} not found.`);
    }
    const errorData = await response.json().catch(() => null);
    throw new Error(errorData?.detail || `Failed to fetch record (HTTP ${response.status})`);
  }
  return response.json();
}

/**
 * Delete a verification record by ID.
 */
export async function deleteVerification(id: number): Promise<void> {
  const response = await fetch(`${BASE_URL}/api/verifications/${id}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error(`Verification record #${id} not found.`);
    }
    const errorData = await response.json().catch(() => null);
    throw new Error(errorData?.detail || `Failed to delete record (HTTP ${response.status})`);
  }
}

/**
 * Check backend service health.
 */
export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(`${BASE_URL}/api/health`);
  if (!response.ok) {
    throw new Error(`Health check failed (HTTP ${response.status})`);
  }
  return response.json();
}
