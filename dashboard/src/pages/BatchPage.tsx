import React, { useState } from 'react';
import { BatchTriageResponse, BatchTriageItemResult } from '../types/api';
import localopsClient from '../api/localopsClient';
import { SeverityBadge, IncidentTypeBadge } from '../components/StatusBadge';
import { EvidencePanel } from '../components/EvidencePanel';
import { ErrorBanner } from '../components/ErrorBanner';
import { downloadJSON, downloadCSV } from '../utils/export';

export const BatchPage: React.FC = () => {
  const [inputText, setInputText] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [batchResponse, setBatchResponse] = useState<BatchTriageResponse | null>(null);
  const [expandedRows, setExpandedRows] = useState<Record<string, boolean>>({});

  const toggleRow = (id: string) => {
    setExpandedRows((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const parseLogs = (text: string): Array<{ raw_log: string; request_id?: string }> => {
    const trimmed = text.trim();
    if (!trimmed) return [];

    // Try parsing as JSON array
    if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
      try {
        const parsed = JSON.parse(trimmed);
        if (Array.isArray(parsed)) {
          return parsed.map((item, idx) => {
            if (typeof item === 'string') {
              return { raw_log: item, request_id: `batch_item_${idx + 1}` };
            }
            return {
              raw_log: item.raw_log || item.log || JSON.stringify(item),
              request_id: item.request_id || `batch_item_${idx + 1}`,
            };
          });
        }
      } catch {
        // Not valid JSON array, fallback to delimiter parsing
      }
    }

    // Try JSON lines (jsonl)
    const lines = trimmed.split('\n').map((l) => l.trim()).filter(Boolean);
    const jsonlItems: Array<{ raw_log: string; request_id?: string }> = [];
    let isAllJson = true;

    for (let i = 0; i < lines.length; i++) {
      try {
        const obj = JSON.parse(lines[i]);
        jsonlItems.push({
          raw_log: obj.raw_log || obj.log || obj.message || lines[i],
          request_id: obj.request_id || `item_${i + 1}`,
        });
      } catch {
        isAllJson = false;
        break;
      }
    }

    if (isAllJson && jsonlItems.length > 0) {
      return jsonlItems;
    }

    // Delimited by double newline or '---'
    if (trimmed.includes('---')) {
      return trimmed
        .split(/---+/)
        .map((block) => block.trim())
        .filter(Boolean)
        .map((log, idx) => ({ raw_log: log, request_id: `item_${idx + 1}` }));
    }

    return trimmed
      .split(/\n\s*\n/)
      .map((block) => block.trim())
      .filter(Boolean)
      .map((log, idx) => ({ raw_log: log, request_id: `item_${idx + 1}` }));
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      if (content) {
        setInputText(content);
        setError(null);
      }
    };
    reader.onerror = () => {
      setError('Failed to read uploaded file.');
    };
    reader.readAsText(file);
  };

  const handleProcessBatch = async () => {
    const items = parseLogs(inputText);
    if (items.length === 0) {
      setError('No valid log entries detected. Provide logs separated by blank lines or JSON.');
      return;
    }
    if (items.length > 16) {
      setError(`Batch size is ${items.length} items. Phase 13 maximum batch limit is 16 items.`);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const resp = await localopsClient.triageBatch(items);
      setBatchResponse(resp);
    } catch (err: any) {
      setError(err.message || 'Error occurred during batch inference execution.');
    } finally {
      setLoading(false);
    }
  };

  const handleExportCSV = () => {
    if (!batchResponse) return;
    const rows = batchResponse.items.map((item) => ({
      request_id: item.request_id,
      status: item.status,
      incident_type: item.result?.incident_type || 'N/A',
      severity: item.result?.severity || 'N/A',
      affected_service: item.result?.affected_service || 'N/A',
      confidence: item.result?.confidence !== undefined ? (item.result.confidence * 100).toFixed(1) + '%' : 'N/A',
      latency_ms: item.inference?.latency_ms ?? 'N/A',
      root_cause: item.result?.root_cause || item.error?.message || 'N/A',
      suggested_action: item.result?.suggested_action || 'N/A',
    }));
    downloadCSV(`localops_batch_${batchResponse.request_id}`, rows);
  };

  const handleExportJSON = () => {
    if (!batchResponse) return;
    downloadJSON(`localops_batch_${batchResponse.request_id}`, batchResponse);
  };

  const parsedItems = parseLogs(inputText);

  return (
    <div className="page-view">
      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      <div className="glass-card">
        <div className="glass-card-header">
          <div>
            <h2 className="card-title">📦 Batch Incident Analysis</h2>
            <p className="card-subtitle">
              Submit multi-incident batches (up to 16 items) with micro-batching and per-item error isolation
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <label className="btn btn-secondary btn-sm" style={{ cursor: 'pointer' }}>
              📁 Upload (.txt/.log/.json)
              <input
                type="file"
                accept=".txt,.log,.json,.jsonl"
                onChange={handleFileUpload}
                style={{ display: 'none' }}
              />
            </label>
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => {
                setInputText('');
                setBatchResponse(null);
                setError(null);
              }}
              disabled={loading || (!inputText && !batchResponse)}
            >
              Clear
            </button>
          </div>
        </div>

        <div className="form-group" style={{ marginBottom: '1rem' }}>
          <div className="form-label">
            <span>PASTE LOG BLOCKS (SEPARATED BY BLANK LINES OR JSON ARRAY)</span>
            <span style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
              Detected: {parsedItems.length} / 16 items
            </span>
          </div>
          <textarea
            className="log-input"
            rows={8}
            placeholder={`Log 1: 2026-09-18T10:14:02Z [order-service] [ERROR] HikariCP connection pool exhausted...

Log 2: 2026-09-18T10:18:22Z [k8s-node-04] [WARNING] kernel: Memory cgroup out of memory: Killed process...

Log 3: 2026-09-18T10:25:31Z [payment-gateway] [ERROR] Tomcat thread pool exhausted...`}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            disabled={loading}
          />
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <button
            className="btn btn-primary"
            onClick={handleProcessBatch}
            disabled={loading || parsedItems.length === 0 || parsedItems.length > 16}
          >
            {loading ? <span className="spinner" /> : <span>⚡</span>}
            Analyze Batch ({parsedItems.length} Incidents)
          </button>
        </div>
      </div>

      {loading && (
        <div className="glass-card" style={{ textAlign: 'center', padding: '2.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '1rem' }}>
            <div className="spinner" style={{ width: '32px', height: '32px', borderWidth: '3px' }} />
          </div>
          <div style={{ fontSize: '1rem', fontWeight: 600 }}>Processing Micro-Batches On GPU...</div>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: '0.35rem' }}>
            Safely executing autoregressive generation with VRAM protection
          </p>
        </div>
      )}

      {batchResponse && !loading && (
        <div className="glass-card">
          <div className="glass-card-header">
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Batch Results Summary</h3>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  ID: {batchResponse.request_id}
                </span>
              </div>
              <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                Total: {batchResponse.total_items} | Successful: {batchResponse.successful_items} | Failed: {batchResponse.failed_items}
              </div>
            </div>

            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button className="btn btn-secondary btn-sm" onClick={handleExportCSV}>
                📊 Export CSV
              </button>
              <button className="btn btn-secondary btn-sm" onClick={handleExportJSON}>
                💾 Export JSON
              </button>
            </div>
          </div>

          <div className="data-table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: '40px' }}></th>
                  <th>Request ID</th>
                  <th>Type</th>
                  <th>Severity</th>
                  <th>Service</th>
                  <th>Confidence</th>
                  <th>Latency</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {batchResponse.items.map((item: BatchTriageItemResult) => {
                  const isExpanded = !!expandedRows[item.request_id];
                  const res = item.result;

                  return (
                    <React.Fragment key={item.request_id}>
                      <tr
                        style={{ cursor: 'pointer', background: isExpanded ? 'rgba(255, 255, 255, 0.03)' : undefined }}
                        onClick={() => toggleRow(item.request_id)}
                      >
                        <td style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
                          {isExpanded ? '▼' : '▶'}
                        </td>
                        <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--text-code)' }}>
                          {item.request_id}
                        </td>
                        <td>
                          {res ? <IncidentTypeBadge type={res.incident_type} /> : '—'}
                        </td>
                        <td>
                          {res ? <SeverityBadge severity={res.severity} /> : '—'}
                        </td>
                        <td style={{ fontWeight: 600 }}>
                          {res?.affected_service || '—'}
                        </td>
                        <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.82rem' }}>
                          {res ? `${(res.confidence * 100).toFixed(0)}%` : '—'}
                        </td>
                        <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.82rem' }}>
                          {item.inference ? `${item.inference.latency_ms} ms` : '—'}
                        </td>
                        <td>
                          <span
                            style={{
                              padding: '0.2rem 0.5rem',
                              borderRadius: '4px',
                              fontSize: '0.72rem',
                              fontWeight: 700,
                              fontFamily: 'var(--font-mono)',
                              background: item.status === 'success' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(244, 63, 94, 0.15)',
                              color: item.status === 'success' ? '#6ee7b7' : '#fda4af',
                              border: `1px solid ${item.status === 'success' ? '#10b981' : '#f43f5e'}`,
                            }}
                          >
                            {item.status.toUpperCase()}
                          </span>
                        </td>
                      </tr>

                      {isExpanded && (
                        <tr>
                          <td colSpan={8} style={{ padding: '1rem 1.5rem', background: 'var(--bg-inset)' }}>
                            {res ? (
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
                                <div className="grid-2">
                                  <div>
                                    <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#f43f5e', marginBottom: '0.25rem' }}>
                                      ROOT CAUSE:
                                    </div>
                                    <div style={{ fontSize: '0.85rem', color: '#f8fafc' }}>
                                      {res.root_cause}
                                    </div>
                                  </div>
                                  <div>
                                    <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#38bdf8', marginBottom: '0.25rem' }}>
                                      SUGGESTED ACTION:
                                    </div>
                                    <div style={{ fontSize: '0.85rem', color: '#f8fafc' }}>
                                      {res.suggested_action}
                                    </div>
                                  </div>
                                </div>

                                <div>
                                  <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
                                    EVIDENCE EXCERPTS:
                                  </div>
                                  <EvidencePanel evidence={res.evidence} />
                                </div>
                              </div>
                            ) : (
                              <div style={{ color: '#fda4af', fontSize: '0.85rem' }}>
                                <strong>Error:</strong> {item.error?.code} — {item.error?.message}
                              </div>
                            )}
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
