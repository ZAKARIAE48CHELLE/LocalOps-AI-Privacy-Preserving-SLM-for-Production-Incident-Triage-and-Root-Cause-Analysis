import React from 'react';
import {
  HealthResponse,
  ReadinessResponse,
  ModelInfoResponse,
  LiveTelemetrySummary,
} from '../types/api';
import { TelemetryCard } from '../components/TelemetryCard';
import { StatusDot } from '../components/StatusBadge';

interface OverviewPageProps {
  health: HealthResponse | null;
  readiness: ReadinessResponse | null;
  modelInfo: ModelInfoResponse | null;
  telemetry: LiveTelemetrySummary | null;
  onNavigate: (tab: 'triage' | 'batch' | 'monitoring' | 'runbooks') => void;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({
  health,
  readiness,
  modelInfo,
  telemetry,
  onNavigate,
}) => {
  const isHealthy = health?.status === 'ok';
  const isReady = readiness?.ready ?? false;
  const systemStatusOnline = isHealthy && isReady;
  const gpu = telemetry?.gpu;

  const vramUsedGb = gpu?.memory_used_bytes
    ? (gpu.memory_used_bytes / (1024 * 1024 * 1024)).toFixed(2)
    : '0.00';
  const vramTotalGb = gpu?.memory_total_bytes
    ? (gpu.memory_total_bytes / (1024 * 1024 * 1024)).toFixed(2)
    : '0.00';
  const vramPercent = gpu?.memory_utilization_percent ?? 0;

  const uptimeHours = telemetry?.uptime_seconds
    ? (telemetry.uptime_seconds / 3600).toFixed(1)
    : '0.0';

  return (
    <div className="page-view">
      {/* Top Banner / System State */}
      <div className="glass-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.35rem' }}>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700 }}>Operational Status: {systemStatusOnline ? 'Active' : 'Standby'}</h2>
            <StatusDot status={systemStatusOnline ? 'online' : 'warning'} label={systemStatusOnline ? 'Inference Engine Ready' : 'Standby / Loading'} />
          </div>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Serving Qwen2.5-1.5B-Instruct fine-tuned with 4-bit QLoRA. Zero cloud telemetry exfiltration.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button className="btn btn-primary" onClick={() => onNavigate('triage')}>
            <span>⚡</span> Start Incident Triage
          </button>
          <button className="btn btn-secondary" onClick={() => onNavigate('batch')}>
            <span>📦</span> Batch Analysis
          </button>
        </div>
      </div>

      {/* Primary KPI Grid */}
      <div className="stats-grid">
        <TelemetryCard
          label="Total Requests"
          value={telemetry?.total_requests ?? 0}
          subtext={`Errors: ${telemetry?.total_errors ?? 0} (${telemetry?.schema_invalid_count ?? 0} schema invalid)`}
          icon="📈"
          highlight={true}
        />
        <TelemetryCard
          label="Latency P50"
          value={telemetry ? `${telemetry.latency_p50_ms} ms` : '—'}
          subtext={`Mean: ${telemetry?.latency_mean_ms ?? 0} ms | P95: ${telemetry?.latency_p95_ms ?? 0} ms`}
          color="var(--accent-cyan)"
          icon="⏱️"
        />
        <TelemetryCard
          label="GPU VRAM Usage"
          value={`${vramUsedGb} / ${vramTotalGb} GB`}
          subtext={`${vramPercent}% utilization | Temp: ${gpu?.temperature_celsius ?? 0}°C`}
          color="var(--accent-purple)"
          icon="🎮"
        />
        <TelemetryCard
          label="Uptime"
          value={`${uptimeHours} hrs`}
          subtext={`Active In-Flight: ${telemetry?.inflight_requests ?? 0}`}
          color="var(--accent-emerald)"
          icon="⏳"
        />
      </div>

      {/* Model & Architecture Details */}
      <div className="grid-2">
        <div className="glass-card">
          <div className="glass-card-header">
            <div>
              <div className="card-title">🤖 Active SLM Weights & Architecture</div>
              <div className="card-subtitle">Validated checkpoint selected from Phase 5 QLoRA</div>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.85rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.5rem', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--text-muted)' }}>Base Model ID</span>
              <span style={{ fontFamily: 'var(--font-mono)', color: '#38bdf8' }}>{modelInfo?.base_model_id || 'Qwen/Qwen2.5-1.5B-Instruct'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.5rem', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--text-muted)' }}>Adapter Identifier</span>
              <span style={{ fontFamily: 'var(--font-mono)' }}>{modelInfo?.adapter_identifier || 'localops-qlora-adapter'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.5rem', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--text-muted)' }}>Source Checkpoint</span>
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-emerald)' }}>{modelInfo?.adapter_source_checkpoint || 'checkpoint-100'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.5rem', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--text-muted)' }}>Quantization Precision</span>
              <span style={{ fontFamily: 'var(--font-mono)' }}>{modelInfo?.quantization_mode || '4-bit NF4 (bitsandbytes)'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.5rem', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--text-muted)' }}>Inference Hardware</span>
              <span style={{ fontFamily: 'var(--font-mono)' }}>{gpu?.device_name || modelInfo?.device || 'CUDA GPU'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Decoding Mode</span>
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)' }}>{modelInfo?.decoding_mode || 'deterministic_greedy'}</span>
            </div>
          </div>
        </div>

        {/* RAG Knowledge Base Status */}
        <div className="glass-card">
          <div className="glass-card-header">
            <div>
              <div className="card-title">📖 Hybrid RAG Runbook Engine</div>
              <div className="card-subtitle">Grounding incident remediation in operational playbooks</div>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.85rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.5rem', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--text-muted)' }}>RAG Requests Total</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{telemetry?.rag.requests_total ?? 0}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.5rem', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--text-muted)' }}>RAG No-Hit Total</span>
              <span style={{ fontFamily: 'var(--font-mono)' }}>{telemetry?.rag.no_hit_total ?? 0}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.5rem', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--text-muted)' }}>Total Prompt Tokens Processed</span>
              <span style={{ fontFamily: 'var(--font-mono)' }}>{telemetry?.prompt_tokens_total ?? 0}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.5rem', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--text-muted)' }}>Total Generated Tokens</span>
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-purple)' }}>{telemetry?.generated_tokens_total ?? 0}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Readiness Checks</span>
              <span style={{ color: readiness?.warmup_completed ? 'var(--accent-emerald)' : 'var(--accent-amber)', fontWeight: 600 }}>
                {readiness?.warmup_completed ? 'Warmup Completed (100%)' : 'Pending'}
              </span>
            </div>
          </div>

          <div style={{ marginTop: '1.25rem' }}>
            <button className="btn btn-secondary btn-sm" onClick={() => onNavigate('runbooks')} style={{ width: '100%' }}>
              Browse 10 Indexed Operational Runbooks →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
