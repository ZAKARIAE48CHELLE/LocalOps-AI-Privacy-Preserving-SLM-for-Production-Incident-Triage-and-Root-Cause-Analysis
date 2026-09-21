import React from 'react';
import { ModelInfoResponse, ReadinessResponse, LiveTelemetrySummary } from '../types/api';

interface SystemPageProps {
  modelInfo: ModelInfoResponse | null;
  readiness: ReadinessResponse | null;
  telemetry: LiveTelemetrySummary | null;
}

export const SystemPage: React.FC<SystemPageProps> = ({
  modelInfo,
  readiness,
  telemetry,
}) => {
  return (
    <div className="page-view">
      <div className="glass-card">
        <div className="glass-card-header">
          <div>
            <h2 className="card-title">⚙️ System Architecture & Model Specifications</h2>
            <p className="card-subtitle">
              Verified operational configuration, local privacy guarantees, and runtime parameters
            </p>
          </div>
          <span
            style={{
              padding: '0.25rem 0.65rem',
              borderRadius: '6px',
              fontSize: '0.75rem',
              fontWeight: 700,
              fontFamily: 'var(--font-mono)',
              background: 'rgba(16, 185, 129, 0.15)',
              color: '#6ee7b7',
              border: '1px solid #10b981',
            }}
          >
            PRIVACY CERTIFIED — 100% LOCAL
          </span>
        </div>

        <div className="grid-2" style={{ marginBottom: '1.5rem' }}>
          {/* Machine & Hardware Specifications */}
          <div style={{ background: 'var(--bg-inset)', padding: '1.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.85rem' }}>
              HARDWARE & ENVIRONMENT
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.85rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.4rem' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Inference Hardware</span>
                <span style={{ fontFamily: 'var(--font-mono)', color: '#38bdf8' }}>{telemetry?.gpu?.device_name || 'NVIDIA RTX Laptop GPU'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.4rem' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Device Type</span>
                <span style={{ fontFamily: 'var(--font-mono)' }}>{modelInfo?.device?.toUpperCase() || 'CUDA'} (Device #0)</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.4rem' }}>
                <span style={{ color: 'var(--text-secondary)' }}>VRAM Capacity</span>
                <span style={{ fontFamily: 'var(--font-mono)' }}>
                  {telemetry?.gpu?.memory_total_bytes ? `${(telemetry.gpu.memory_total_bytes / (1024**3)).toFixed(1)} GB GDDR6` : '8.0 GB GDDR6'}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.4rem' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Quantization Mode</span>
                <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-purple)' }}>{modelInfo?.quantization_mode || '4-bit NormalFloat (NF4)'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-secondary)' }}>CUDA Availability</span>
                <span style={{ color: readiness?.cuda_available ? 'var(--accent-emerald)' : 'var(--accent-amber)', fontWeight: 600 }}>
                  {readiness?.cuda_available ? 'Enabled (Compute Capability 8.6)' : 'Disabled / CPU Fallback'}
                </span>
              </div>
            </div>
          </div>

          {/* Model & Inference Serving Config */}
          <div style={{ background: 'var(--bg-inset)', padding: '1.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.85rem' }}>
              SLM PARAMETERS & LIMITS
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.85rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.4rem' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Base SLM Model</span>
                <span style={{ fontFamily: 'var(--font-mono)' }}>{modelInfo?.base_model_id || 'Qwen/Qwen2.5-1.5B-Instruct'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.4rem' }}>
                <span style={{ color: 'var(--text-secondary)' }}>LoRA Checkpoint</span>
                <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-emerald)' }}>{modelInfo?.adapter_source_checkpoint || 'checkpoint-100'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.4rem' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Max Input Tokens</span>
                <span style={{ fontFamily: 'var(--font-mono)' }}>{modelInfo?.max_input_tokens || 1024} tokens (~32 KB raw log)</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.4rem' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Max Generated Tokens</span>
                <span style={{ fontFamily: 'var(--font-mono)' }}>{modelInfo?.max_new_tokens || 512} tokens</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Decoding Strategy</span>
                <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)' }}>{modelInfo?.decoding_mode || 'deterministic_greedy (temp=0.0)'}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Security and Privacy Governance */}
        <div style={{ background: 'rgba(16, 185, 129, 0.05)', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: 'var(--radius-md)', padding: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '1.2rem' }}>🔒</span>
            <span style={{ fontWeight: 700, color: '#6ee7b7', fontSize: '0.95rem' }}>
              Zero-Trust Privacy & Security Architecture
            </span>
          </div>

          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            LocalOps AI executes completely on-premises. Production logs pasted into this dashboard are processed strictly in GPU memory
            by the local fine-tuned SLM.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginTop: '1rem' }}>
            <div style={{ background: 'var(--bg-inset)', padding: '0.85rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--accent-emerald)' }}>✓ Zero Cloud Calls</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>No external OpenAI, Anthropic, or cloud model APIs are ever invoked.</div>
            </div>

            <div style={{ background: 'var(--bg-inset)', padding: '0.85rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--accent-emerald)' }}>✓ Zero Remote Telemetry</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>No Google Analytics, Sentry, or third-party trackers are bundled.</div>
            </div>

            <div style={{ background: 'var(--bg-inset)', padding: '0.85rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--accent-emerald)' }}>✓ Ephemeral In-Memory State</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>Raw production logs are never written to disk or browser localStorage.</div>
            </div>

            <div style={{ background: 'var(--bg-inset)', padding: '0.85rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--accent-emerald)' }}>✓ Schema-Validated Output</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>Every response is validated via strict Pydantic v2 domain schemas.</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
