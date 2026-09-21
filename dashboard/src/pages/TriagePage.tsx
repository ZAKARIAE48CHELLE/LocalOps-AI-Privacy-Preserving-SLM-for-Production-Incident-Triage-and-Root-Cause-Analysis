import React, { useState } from 'react';
import {
  TriageResponse,
  EnrichedTriageResponse,
} from '../types/api';
import localopsClient from '../api/localopsClient';
import { SeverityBadge, IncidentTypeBadge } from '../components/StatusBadge';
import { EvidencePanel } from '../components/EvidencePanel';
import { RemediationPanel } from '../components/RemediationPanel';
import { SampleIncidentPicker } from '../components/SampleIncidentPicker';
import { SampleIncident } from '../utils/sampleIncidents';
import { ErrorBanner } from '../components/ErrorBanner';
import { downloadJSON, copyToClipboard } from '../utils/export';

const MAX_LOG_LENGTH = 32768;

export const TriagePage: React.FC = () => {
  const [rawLog, setRawLog] = useState<string>('');
  const [requestId, setRequestId] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [triageData, setTriageData] = useState<TriageResponse | EnrichedTriageResponse | null>(null);
  const [isEnriched, setIsEnriched] = useState<boolean>(false);
  const [copiedSummary, setCopiedSummary] = useState<boolean>(false);

  const charCount = rawLog.length;
  const isOverLimit = charCount > MAX_LOG_LENGTH;

  const handleSelectSample = (sample: SampleIncident) => {
    setRawLog(sample.rawLog);
    setRequestId(`sample_${sample.id}_${Date.now().toString().slice(-4)}`);
    setError(null);
  };

  const handleClear = () => {
    setRawLog('');
    setRequestId('');
    setError(null);
    setTriageData(null);
  };

  const handleTriage = async (enriched: boolean) => {
    if (!rawLog.trim()) {
      setError('Please provide a raw log payload to analyze.');
      return;
    }
    if (isOverLimit) {
      setError(`Log payload exceeds maximum allowed size of ${MAX_LOG_LENGTH} characters.`);
      return;
    }

    setLoading(true);
    setError(null);
    setIsEnriched(enriched);

    try {
      if (enriched) {
        const resp = await localopsClient.triageEnriched(rawLog, requestId || undefined);
        setTriageData(resp);
      } else {
        const resp = await localopsClient.triage(rawLog, requestId || undefined);
        setTriageData(resp);
      }
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred during incident analysis.');
    } finally {
      setLoading(false);
    }
  };

  const handleExportJSON = () => {
    if (!triageData) return;
    downloadJSON(`localops_triage_${triageData.request_id}`, triageData);
  };

  const handleCopyReport = async () => {
    if (!triageData) return;
    const r = triageData.result;
    const report = `[LOCALOPS AI INCIDENT TRIAGE REPORT]
Request ID: ${triageData.request_id}
Incident Type: ${r.incident_type}
Severity: ${r.severity}
Affected Service: ${r.affected_service}
Confidence: ${(r.confidence * 100).toFixed(1)}%
Latency: ${triageData.inference.latency_ms} ms

ROOT CAUSE:
${r.root_cause}

SUGGESTED ACTION:
${r.suggested_action}

EVIDENCE:
${r.evidence.map((e, i) => `[${i + 1}] ${e}`).join('\n')}
`;
    const ok = await copyToClipboard(report);
    if (ok) {
      setCopiedSummary(true);
      setTimeout(() => setCopiedSummary(false), 2000);
    }
  };

  return (
    <div className="page-view">
      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {/* Input Section */}
      <div className="glass-card">
        <div className="glass-card-header">
          <div>
            <h2 className="card-title">⚡ Incident Log Analysis</h2>
            <p className="card-subtitle">
              Paste raw stack traces, log lines, or kernel events for deterministic local SLM triage
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={handleClear}
              disabled={loading || (!rawLog && !triageData)}
            >
              Clear
            </button>
          </div>
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <SampleIncidentPicker onSelect={handleSelectSample} disabled={loading} />
        </div>

        <div className="form-group" style={{ marginBottom: '1rem' }}>
          <div className="form-label">
            <span>RAW PRODUCTION LOG TEXT</span>
            <span className={`char-counter ${charCount > MAX_LOG_LENGTH * 0.9 ? 'warning' : ''}`}>
              {charCount} / {MAX_LOG_LENGTH} chars
            </span>
          </div>
          <textarea
            className="log-input"
            rows={7}
            placeholder="Paste production log excerpt here... e.g. 2026-09-18T10:14:02.112Z [order-service] [ERROR] HikariCP Failed to acquire connection..."
            value={rawLog}
            onChange={(e) => setRawLog(e.target.value)}
            disabled={loading}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Request ID:</span>
            <input
              type="text"
              className="text-input"
              style={{ width: '220px', padding: '0.4rem 0.65rem' }}
              placeholder="Auto-generated if empty"
              value={requestId}
              onChange={(e) => setRequestId(e.target.value)}
              disabled={loading}
            />
          </div>

          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => handleTriage(false)}
              disabled={loading || !rawLog.trim() || isOverLimit}
            >
              {loading && !isEnriched ? <span className="spinner" /> : <span>🔍</span>}
              Analyze Incident
            </button>

            <button
              type="button"
              className="btn btn-primary"
              onClick={() => handleTriage(true)}
              disabled={loading || !rawLog.trim() || isOverLimit}
            >
              {loading && isEnriched ? <span className="spinner" /> : <span>🛡️</span>}
              Analyze + Runbook
            </button>
          </div>
        </div>
      </div>

      {/* Loading Indicator */}
      {loading && (
        <div className="glass-card" style={{ textAlign: 'center', padding: '2.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '1rem' }}>
            <div className="spinner" style={{ width: '32px', height: '32px', borderWidth: '3px' }} />
          </div>
          <div style={{ fontSize: '1rem', fontWeight: 600 }}>Executing On-Device SLM Inference...</div>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: '0.35rem' }}>
            Querying Qwen2.5-1.5B with 4-bit QLoRA adapter and Pydantic validation
          </p>
        </div>
      )}

      {/* Triage Results Display */}
      {triageData && !loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Summary Card */}
          <div className="glass-card" style={{ border: '1px solid rgba(56, 189, 248, 0.4)' }}>
            <div className="glass-card-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                <IncidentTypeBadge type={triageData.result.incident_type} />
                <SeverityBadge severity={triageData.result.severity} />
                <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  Service: <strong style={{ color: '#fff' }}>{triageData.result.affected_service}</strong>
                </span>
              </div>

              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button className="btn btn-secondary btn-sm" onClick={handleCopyReport}>
                  {copiedSummary ? '✓ Copied' : '📋 Copy Report'}
                </button>
                <button className="btn btn-secondary btn-sm" onClick={handleExportJSON}>
                  💾 Export JSON
                </button>
              </div>
            </div>

            <div className="stats-grid" style={{ marginBottom: '1.25rem' }}>
              <div className="stat-card">
                <span className="stat-label">Model Confidence</span>
                <span className="stat-value" style={{ color: 'var(--accent-emerald)' }}>
                  {(triageData.result.confidence * 100).toFixed(1)}%
                </span>
                <span className="stat-subtext">Reported score [0.0 - 1.0]</span>
              </div>

              <div className="stat-card">
                <span className="stat-label">Inference Latency</span>
                <span className="stat-value" style={{ color: 'var(--accent-cyan)' }}>
                  {triageData.inference.latency_ms} ms
                </span>
                <span className="stat-subtext">
                  Tokens: {triageData.inference.prompt_tokens} prompt / {triageData.inference.generated_tokens} gen
                </span>
              </div>

              <div className="stat-card">
                <span className="stat-label">Tracking Request ID</span>
                <span className="stat-value" style={{ fontSize: '1rem', color: 'var(--text-code)' }}>
                  {triageData.request_id}
                </span>
                <span className="stat-subtext">X-Request-ID trace header</span>
              </div>
            </div>

            {/* Root Cause & Suggested Action */}
            <div className="grid-2">
              <div style={{ background: 'var(--bg-inset)', padding: '1.15rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: '#f43f5e', marginBottom: '0.4rem', letterSpacing: '0.05em' }}>
                  🎯 DIAGNOSED ROOT CAUSE
                </div>
                <div style={{ fontSize: '0.9rem', lineHeight: 1.6, color: '#f8fafc' }}>
                  {triageData.result.root_cause}
                </div>
              </div>

              <div style={{ background: 'var(--bg-inset)', padding: '1.15rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: '#38bdf8', marginBottom: '0.4rem', letterSpacing: '0.05em' }}>
                  ⚡ IMMEDIATE SUGGESTED ACTION
                </div>
                <div style={{ fontSize: '0.9rem', lineHeight: 1.6, color: '#f8fafc' }}>
                  {triageData.result.suggested_action}
                </div>
                <div className="advisory-notice">
                  Advisory only — LocalOps AI does not execute production changes.
                </div>
              </div>
            </div>

            {/* Evidence Monospace Excerpts */}
            <div style={{ marginTop: '1.5rem' }}>
              <div style={{ fontSize: '0.8rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: '0.6rem' }}>
                SUPPORTING LOG EVIDENCE EXCERPTS ({triageData.result.evidence.length})
              </div>
              <EvidencePanel evidence={triageData.result.evidence} />
            </div>
          </div>

          {/* Enriched RAG Remediation if present */}
          {'remediation' in triageData && (
            <RemediationPanel remediation={(triageData as EnrichedTriageResponse).remediation} />
          )}
        </div>
      )}
    </div>
  );
};
