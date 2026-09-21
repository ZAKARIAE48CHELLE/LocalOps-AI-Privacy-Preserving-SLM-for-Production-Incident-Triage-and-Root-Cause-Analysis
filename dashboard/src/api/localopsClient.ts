/**
 * LocalOps AI — Typed REST API Client
 * Interacts with FastAPI backend without loading model weights or altering semantics.
 */

import {
  HealthResponse,
  ReadinessResponse,
  ModelInfoResponse,
  LiveTelemetrySummary,
  TriageResponse,
  EnrichedTriageResponse,
  BatchTriageResponse,
  RunbookMetadata,
  ErrorResponse,
} from '../types/api';

class LocalOpsClient {
  private baseUrl: string;

  constructor(baseUrl: string = '') {
    this.baseUrl = baseUrl;
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const headers = {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...(options.headers || {}),
    };

    let response: Response;
    try {
      response = await fetch(url, { ...options, headers });
    } catch (err: any) {
      throw new Error(`Network error connecting to LocalOps AI backend: ${err.message || err}`);
    }

    if (!response.ok) {
      let errorData: ErrorResponse | null = null;
      try {
        errorData = await response.json();
      } catch {
        // Not JSON
      }

      if (errorData && errorData.error) {
        throw new Error(`[${errorData.error.code}] ${errorData.error.message}`);
      }

      if (response.status === 413) {
        throw new Error('[PAYLOAD_TOO_LARGE] Log content exceeds maximum allowed buffer size.');
      }
      if (response.status === 503) {
        throw new Error('[MODEL_NOT_READY] Model is currently loading or warming up.');
      }
      if (response.status === 507) {
        throw new Error('[INSUFFICIENT_STORAGE] GPU VRAM or resources exhausted.');
      }
      if (response.status === 502) {
        throw new Error('[MODEL_OUTPUT_INVALID] Model generated unparseable output after retries.');
      }

      throw new Error(`HTTP Error ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  public async getHealth(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/health');
  }

  public async getReadiness(): Promise<ReadinessResponse> {
    return this.request<ReadinessResponse>('/ready');
  }

  public async getModelInfo(): Promise<ModelInfoResponse> {
    return this.request<ModelInfoResponse>('/api/v1/model-info');
  }

  public async getLiveTelemetry(): Promise<LiveTelemetrySummary> {
    return this.request<LiveTelemetrySummary>('/api/v1/telemetry/live');
  }

  public async getPrometheusMetrics(): Promise<string> {
    const res = await fetch(`${this.baseUrl}/metrics`);
    if (!res.ok) {
      throw new Error(`Failed to fetch Prometheus metrics: HTTP ${res.status}`);
    }
    return res.text();
  }

  public async triage(rawLog: string, requestId?: string): Promise<TriageResponse> {
    return this.request<TriageResponse>('/api/v1/triage', {
      method: 'POST',
      body: JSON.stringify({
        raw_log: rawLog,
        request_id: requestId || undefined,
      }),
    });
  }

  public async triageEnriched(rawLog: string, requestId?: string): Promise<EnrichedTriageResponse> {
    return this.request<EnrichedTriageResponse>('/api/v1/triage/enriched', {
      method: 'POST',
      body: JSON.stringify({
        raw_log: rawLog,
        request_id: requestId || undefined,
      }),
    });
  }

  public async triageBatch(
    items: Array<{ raw_log: string; request_id?: string }>
  ): Promise<BatchTriageResponse> {
    return this.request<BatchTriageResponse>('/api/v1/triage/batch', {
      method: 'POST',
      body: JSON.stringify({ items }),
    });
  }

  public async listRunbooks(): Promise<RunbookMetadata[]> {
    return this.request<RunbookMetadata[]>('/api/v1/runbooks');
  }

  public async getRunbook(runbookId: string): Promise<RunbookMetadata> {
    return this.request<RunbookMetadata>(`/api/v1/runbooks/${encodeURIComponent(runbookId)}`);
  }
}

export const localopsClient = new LocalOpsClient();
export default localopsClient;
