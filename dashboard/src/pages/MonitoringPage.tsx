import React, { useState, useEffect } from 'react';
import { LiveTelemetrySummary } from '../types/api';
import localopsClient from '../api/localopsClient';
import { TelemetryCard } from '../components/TelemetryCard';

interface MonitoringPageProps {
  telemetry: LiveTelemetrySummary | null;
}

export const MonitoringPage: React.FC<MonitoringPageProps> = ({ telemetry }) => {
  const [promMetrics, setPromMetrics] = useState<string>('');
  const [activeTab, setActiveTab] = useState<'visual' | 'prometheus'>('visual');
  const [loadingProm, setLoadingProm] = useState<boolean>(false);

  useEffect(() => {
    if (activeTab === 'prometheus') {
      setLoadingProm(true);
      localopsClient.getPrometheusMetrics()
        .then((text) => setPromMetrics(text))
        .catch((err) => setPromMetrics(`Error loading Prometheus metrics: ${err.message}`))
        .finally(() => setLoadingProm(false));
    }
  }, [activeTab]);

  const gpu = telemetry?.gpu;
  const vramUsedGb = gpu?.memory_used_bytes
    ? (gpu.memory_used_bytes / (1024 * 1024 * 1024)).toFixed(2)
    : '0.00';
  const vramTotalGb = gpu?.memory_total_bytes
    ? (gpu.memory_total_bytes / (1024 * 1024 * 1024)).toFixed(2)
    : '0.00';
  const vramPercent = gpu?.memory_utilization_percent ?? 0;

  const typeEntries = Object.entries(telemetry?.predictions_by_type || {});
  const totalPredicted = typeEntries.reduce((sum, [, count]) => sum + count, 0);

  return (
    <div className="page-view">
      <div className="glass-card">
        <div className="glass-card-header">
          <div>
            <h2 className="card-title">📊 Operational Telemetry & GPU Metrics</h2>
            <p className="card-subtitle">
              Live Prometheus counters, autoregressive token velocity, and hardware telemetry
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              className={`btn btn-sm ${activeTab === 'visual' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setActiveTab('visual')}
            >
              Dashboard Visuals
            </button>
            <button
              className={`btn btn-sm ${activeTab === 'prometheus' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setActiveTab('prometheus')}
            >
              Raw Prometheus /metrics
            </button>
          </div>
        </div>

        {activeTab === 'visual' ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            {/* Latency & Throughput KPIs */}
            <div className="stats-grid">
              <TelemetryCard
                label="P50 Latency"
                value={`${telemetry?.latency_p50_ms ?? 0} ms`}
                subtext="Median inference turnaround"
                color="var(--accent-cyan)"
                icon="⏱️"
              />
              <TelemetryCard
                label="P95 Latency"
                value={`${telemetry?.latency_p95_ms ?? 0} ms`}
                subtext="95th percentile turnaround"
                color="var(--accent-amber)"
                icon="📈"
              />
              <TelemetryCard
                label="Generated Tokens"
                value={telemetry?.generated_tokens_total ?? 0}
                subtext={`Prompt tokens: ${telemetry?.prompt_tokens_total ?? 0}`}
                color="var(--accent-purple)"
                icon="🔤"
              />
              <TelemetryCard
                label="Schema Validity"
                value={`${(telemetry?.total_requests ? ((telemetry.total_requests - telemetry.schema_invalid_count) / telemetry.total_requests * 100) : 100).toFixed(1)}%`}
                subtext={`Invalid: ${telemetry?.schema_invalid_count ?? 0} / ${telemetry?.total_requests ?? 0}`}
                color="var(--accent-emerald)"
                icon="✅"
              />
            </div>

            {/* GPU Telemetry Section */}
            <div className="glass-card" style={{ background: 'var(--bg-inset)' }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '1rem', letterSpacing: '0.05em' }}>
                🎮 HARDWARE TELEMETRY & VRAM OCCUPANCY
              </div>

              <div className="stats-grid">
                <div className="stat-card">
                  <span className="stat-label">GPU Model</span>
                  <span className="stat-value" style={{ fontSize: '1.1rem', color: '#fff' }}>
                    {gpu?.device_name || 'NVIDIA RTX Laptop GPU'}
                  </span>
                  <span className="stat-subtext">Device #{gpu?.device_index ?? 0}</span>
                </div>

                <div className="stat-card">
                  <span className="stat-label">VRAM Allocation</span>
                  <span className="stat-value" style={{ color: 'var(--accent-cyan)' }}>
                    {vramUsedGb} GB
                  </span>
                  <span className="stat-subtext">of {vramTotalGb} GB total ({vramPercent}%)</span>
                  {/* Progress bar */}
                  <div style={{ width: '100%', height: '6px', background: 'rgba(255,255,255,0.1)', borderRadius: '3px', marginTop: '0.5rem', overflow: 'hidden' }}>
                    <div
                      style={{
                        width: `${Math.min(vramPercent, 100)}%`,
                        height: '100%',
                        background: vramPercent > 85 ? 'var(--accent-rose)' : 'var(--accent-cyan)',
                        transition: 'width 0.3s ease',
                      }}
                    />
                  </div>
                </div>

                <div className="stat-card">
                  <span className="stat-label">Compute Utilization</span>
                  <span className="stat-value" style={{ color: 'var(--accent-emerald)' }}>
                    {gpu?.utilization_percent ?? 0}%
                  </span>
                  <span className="stat-subtext">CUDA Streaming Multiprocessors</span>
                </div>

                <div className="stat-card">
                  <span className="stat-label">Core Temperature</span>
                  <span className="stat-value" style={{ color: (gpu?.temperature_celsius ?? 0) > 80 ? 'var(--accent-rose)' : '#fff' }}>
                    {gpu?.temperature_celsius ?? 0}°C
                  </span>
                  <span className="stat-subtext">Power: {gpu?.power_watts ? `${gpu.power_watts.toFixed(1)} W` : 'N/A'}</span>
                </div>
              </div>
            </div>

            {/* Predictions by Incident Type Distribution */}
            <div className="glass-card" style={{ background: 'var(--bg-inset)' }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '1rem', letterSpacing: '0.05em' }}>
                📊 CLASSIFICATION TAXONOMY DISTRIBUTION
              </div>

              {typeEntries.length === 0 ? (
                <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', fontStyle: 'italic', padding: '1rem 0' }}>
                  No incident predictions recorded in this session yet. Run incident triage to populate distribution.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {typeEntries.map(([typeName, count]) => {
                    const pct = totalPredicted > 0 ? Math.round((count / totalPredicted) * 100) : 0;
                    return (
                      <div key={typeName}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', marginBottom: '0.25rem' }}>
                          <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{typeName}</span>
                          <span style={{ color: 'var(--text-muted)' }}>{count} ({pct}%)</span>
                        </div>
                        <div style={{ width: '100%', height: '8px', background: 'rgba(255,255,255,0.08)', borderRadius: '4px', overflow: 'hidden' }}>
                          <div
                            style={{
                              width: `${pct}%`,
                              height: '100%',
                              background:
                                typeName === 'DATABASE' ? 'var(--type-db)' :
                                typeName === 'INFRASTRUCTURE' ? 'var(--type-infra)' :
                                typeName === 'APPLICATION' ? 'var(--type-app)' :
                                typeName === 'SECURITY' ? 'var(--type-sec)' :
                                typeName === 'NETWORK' ? 'var(--type-net)' : 'var(--type-msg)',
                            }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div>
            {loadingProm ? (
              <div style={{ padding: '2rem', textAlign: 'center' }}>
                <span className="spinner" />
              </div>
            ) : (
              <pre
                className="code-block"
                style={{
                  maxHeight: '600px',
                  overflowY: 'auto',
                  fontSize: '0.78rem',
                  lineHeight: 1.5,
                  color: '#93c5fd',
                }}
              >
                {promMetrics}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
