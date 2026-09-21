/**
 * LocalOps AI — API TypeScript Contracts
 * Strictly mirrors backend Pydantic schemas.
 */

export type IncidentType =
  | "DATABASE"
  | "INFRASTRUCTURE"
  | "APPLICATION"
  | "SECURITY"
  | "NETWORK"
  | "MESSAGING";

export type Severity =
  | "P1_CRITICAL"
  | "P2_HIGH"
  | "P3_MEDIUM"
  | "P4_LOW";

export interface LogTriageOutput {
  incident_type: IncidentType;
  severity: Severity;
  affected_service: string;
  root_cause: string;
  suggested_action: string;
  confidence: number;
  evidence: string[];
}

export interface InferenceTelemetry {
  latency_ms: number;
  prompt_tokens: number;
  generated_tokens: number;
}

export interface TriageResponse {
  request_id: string;
  result: LogTriageOutput;
  inference: InferenceTelemetry;
}

export interface RemediationRecommendation {
  runbook_document: string;
  runbook_title: string;
  section: string;
  content: string;
  relevance_score: number;
  matched_keywords: string[];
}

export interface EnrichedTriageResponse {
  request_id: string;
  result: LogTriageOutput;
  remediation?: RemediationRecommendation | null;
  inference: InferenceTelemetry;
}

export interface BatchTriageItemResult {
  request_id: string;
  status: "success" | "error";
  result?: LogTriageOutput | null;
  error?: { code: string; message: string } | null;
  inference?: InferenceTelemetry | null;
}

export interface BatchTriageResponse {
  request_id: string;
  total_items: number;
  successful_items: number;
  failed_items: number;
  items: BatchTriageItemResult[];
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  timestamp?: number;
}

export interface ReadinessResponse {
  ready: boolean;
  service: string;
  tokenizer_loaded: boolean;
  base_model_loaded: boolean;
  adapter_loaded: boolean;
  cuda_available: boolean;
  warmup_completed: boolean;
  message: string;
}

export interface ModelInfoResponse {
  base_model_id: string;
  adapter_identifier: string;
  adapter_source_checkpoint: string;
  quantization_mode: string;
  device: string;
  schema_version: string;
  service_version: string;
  max_input_tokens: number;
  max_new_tokens: number;
  decoding_mode: string;
}

export interface GpuTelemetry {
  available: boolean;
  device_name?: string;
  device_index?: number;
  memory_used_bytes?: number;
  memory_total_bytes?: number;
  memory_utilization_percent?: number;
  utilization_percent?: number;
  temperature_celsius?: number;
  power_watts?: number;
  timestamp?: number;
}

export interface LiveTelemetrySummary {
  uptime_seconds: number;
  total_requests: number;
  total_errors: number;
  inflight_requests: number;
  schema_invalid_count: number;
  prompt_tokens_total: number;
  generated_tokens_total: number;
  latency_p50_ms: number;
  latency_p95_ms: number;
  latency_mean_ms: number;
  predictions_by_type: Record<string, number>;
  gpu: GpuTelemetry;
  rag: {
    requests_total: number;
    no_hit_total: number;
  };
}

export interface RunbookSection {
  section: string;
  chunk_id: string;
  content: string;
}

export interface RunbookMetadata {
  runbook_id: string;
  document: string;
  title: string;
  incident_type: string;
  affected_services: string[];
  keywords: string[];
  sections: RunbookSection[];
  raw_markdown?: string;
}

export interface ErrorResponse {
  request_id: string;
  error: {
    code: string;
    message: string;
  };
}
