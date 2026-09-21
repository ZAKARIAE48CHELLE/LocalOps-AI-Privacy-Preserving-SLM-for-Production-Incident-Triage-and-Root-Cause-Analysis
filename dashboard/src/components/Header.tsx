import React from 'react';
import { ReadinessResponse, LiveTelemetrySummary } from '../types/api';

interface HeaderProps {
  title: string;
  subtitle: string;
  readiness: ReadinessResponse | null;
  telemetry: LiveTelemetrySummary | null;
}

export const Header: React.FC<HeaderProps> = ({
  title,
  subtitle,
  readiness,
  telemetry,
}) => {
  const isOnline = readiness?.ready ?? false;
  const vramUsedGb = telemetry?.gpu?.memory_used_bytes
    ? (telemetry.gpu.memory_used_bytes / (1024 * 1024 * 1024)).toFixed(1)
    : null;
  const vramTotalGb = telemetry?.gpu?.memory_total_bytes
    ? (telemetry.gpu.memory_total_bytes / (1024 * 1024 * 1024)).toFixed(1)
    : null;

  return (
    <header className="top-header">
      <div className="header-title-group">
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>

      <div className="header-telemetry-pill">
        <div className="pill-item">
          <span className={`pulse-dot ${isOnline ? 'online' : 'warning'}`} />
          <span style={{ fontWeight: 600, color: isOnline ? 'var(--accent-emerald)' : 'var(--accent-amber)' }}>
            {isOnline ? 'READY' : 'STANDBY'}
          </span>
        </div>

        {vramUsedGb && vramTotalGb && (
          <div className="pill-item">
            <span style={{ color: 'var(--text-muted)' }}>VRAM:</span>
            <span style={{ color: 'var(--text-code)' }}>{vramUsedGb}/{vramTotalGb} GB</span>
          </div>
        )}

        {telemetry && (
          <>
            <div className="pill-item">
              <span style={{ color: 'var(--text-muted)' }}>P50:</span>
              <span style={{ color: 'var(--text-primary)' }}>{telemetry.latency_p50_ms}ms</span>
            </div>
            <div className="pill-item">
              <span style={{ color: 'var(--text-muted)' }}>REQS:</span>
              <span style={{ color: 'var(--text-primary)' }}>{telemetry.total_requests}</span>
            </div>
          </>
        )}
      </div>
    </header>
  );
};
