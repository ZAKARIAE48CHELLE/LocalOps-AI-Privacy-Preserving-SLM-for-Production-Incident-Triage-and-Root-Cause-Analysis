import React, { useState, useEffect } from 'react';
import { RunbookMetadata } from '../types/api';
import localopsClient from '../api/localopsClient';
import { IncidentTypeBadge } from '../components/StatusBadge';
import { copyToClipboard } from '../utils/export';

export const RunbooksPage: React.FC = () => {
  const [runbooks, setRunbooks] = useState<RunbookMetadata[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedRunbook, setSelectedRunbook] = useState<RunbookMetadata | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedType, setSelectedType] = useState<string>('ALL');
  const [copiedSection, setCopiedSection] = useState<string | null>(null);

  useEffect(() => {
    fetchRunbooks();
  }, []);

  const fetchRunbooks = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await localopsClient.listRunbooks();
      setRunbooks(data);
      if (data.length > 0) {
        setSelectedRunbook(data[0]);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load runbooks.');
    } finally {
      setLoading(false);
    }
  };

  const handleCopySection = async (content: string, id: string) => {
    const ok = await copyToClipboard(content);
    if (ok) {
      setCopiedSection(id);
      setTimeout(() => setCopiedSection(null), 2000);
    }
  };

  const filteredRunbooks = runbooks.filter((rb) => {
    const matchesType = selectedType === 'ALL' || rb.incident_type === selectedType;
    const q = searchQuery.toLowerCase();
    const matchesQuery =
      !q ||
      rb.title.toLowerCase().includes(q) ||
      rb.runbook_id.toLowerCase().includes(q) ||
      rb.keywords.some((kw) => kw.toLowerCase().includes(q)) ||
      rb.affected_services.some((s) => s.toLowerCase().includes(q));
    return matchesType && matchesQuery;
  });

  const incidentTypes = ['ALL', 'DATABASE', 'INFRASTRUCTURE', 'APPLICATION', 'SECURITY', 'NETWORK', 'MESSAGING'];

  return (
    <div className="page-view">
      <div className="glass-card">
        <div className="glass-card-header">
          <div>
            <h2 className="card-title">📖 Operational Runbooks Knowledge Base</h2>
            <p className="card-subtitle">
              Pre-indexed playbooks grounded for automated remediation retrieval (Read-Only)
            </p>
          </div>
          <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            Total Runbooks: {runbooks.length}
          </div>
        </div>

        {/* Search & Filter Bar */}
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', marginBottom: '1.25rem' }}>
          <input
            type="text"
            className="text-input"
            style={{ flex: 1, minWidth: '240px' }}
            placeholder="Search runbook title, keyword, or service..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />

          <select
            className="text-input"
            style={{ minWidth: '180px' }}
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
          >
            {incidentTypes.map((t) => (
              <option key={t} value={t}>
                {t === 'ALL' ? 'All Incident Types' : t}
              </option>
            ))}
          </select>
        </div>

        {loading ? (
          <div style={{ padding: '3rem', textAlign: 'center' }}>
            <span className="spinner" />
            <p style={{ marginTop: '0.5rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              Loading operational runbooks from catalog...
            </p>
          </div>
        ) : error ? (
          <div style={{ color: '#fda4af', padding: '1rem', background: 'rgba(244, 63, 94, 0.1)', borderRadius: '8px' }}>
            {error}
          </div>
        ) : (
          <div className="grid-2">
            {/* Runbooks Master List */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '650px', overflowY: 'auto' }}>
              {filteredRunbooks.length === 0 ? (
                <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', fontStyle: 'italic', padding: '1rem' }}>
                  No runbooks match your search criteria.
                </div>
              ) : (
                filteredRunbooks.map((rb) => {
                  const isSelected = selectedRunbook?.runbook_id === rb.runbook_id;
                  return (
                    <div
                      key={rb.runbook_id}
                      onClick={() => setSelectedRunbook(rb)}
                      style={{
                        padding: '0.85rem 1rem',
                        borderRadius: 'var(--radius-md)',
                        background: isSelected ? 'rgba(56, 189, 248, 0.12)' : 'var(--bg-inset)',
                        border: isSelected ? '1px solid var(--accent-cyan)' : '1px solid var(--border-subtle)',
                        cursor: 'pointer',
                        transition: 'all 0.18s ease',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
                        <IncidentTypeBadge type={rb.incident_type} />
                        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                          {rb.document}
                        </span>
                      </div>
                      <div style={{ fontWeight: 600, fontSize: '0.9rem', color: isSelected ? '#fff' : 'var(--text-primary)' }}>
                        {rb.title}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.35rem' }}>
                        Services: {rb.affected_services.join(', ')}
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* Runbook Detail Panel */}
            <div style={{ background: 'var(--bg-inset)', padding: '1.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)', maxHeight: '650px', overflowY: 'auto' }}>
              {selectedRunbook ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
                      <IncidentTypeBadge type={selectedRunbook.incident_type} />
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                        {selectedRunbook.document}
                      </span>
                    </div>
                    <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#f8fafc' }}>
                      {selectedRunbook.title}
                    </h3>
                  </div>

                  {/* Keywords */}
                  <div>
                    <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '0.35rem' }}>
                      RETRIEVAL TRIGGER KEYWORDS:
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
                      {selectedRunbook.keywords.map((kw, i) => (
                        <span
                          key={i}
                          style={{
                            background: 'rgba(255,255,255,0.06)',
                            padding: '0.15rem 0.45rem',
                            borderRadius: '4px',
                            fontSize: '0.72rem',
                            fontFamily: 'var(--font-mono)',
                            color: 'var(--accent-cyan)',
                          }}
                        >
                          {kw}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Sections list */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    {selectedRunbook.sections.map((sec, i) => (
                      <div
                        key={i}
                        style={{
                          background: 'rgba(255, 255, 255, 0.025)',
                          border: '1px solid var(--border-subtle)',
                          borderRadius: 'var(--radius-sm)',
                          padding: '0.85rem',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                          <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#93c5fd' }}>
                            {sec.section}
                          </span>
                          <button
                            className="btn btn-secondary btn-sm"
                            style={{ padding: '0.15rem 0.45rem', fontSize: '0.7rem' }}
                            onClick={() => handleCopySection(sec.content, sec.chunk_id)}
                          >
                            {copiedSection === sec.chunk_id ? '✓ Copied' : 'Copy'}
                          </button>
                        </div>
                        <pre
                          style={{
                            fontFamily: 'var(--font-mono)',
                            fontSize: '0.8rem',
                            lineHeight: 1.5,
                            color: '#cbd5e1',
                            whiteSpace: 'pre-wrap',
                            margin: 0,
                          }}
                        >
                          {sec.content}
                        </pre>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', fontStyle: 'italic' }}>
                  Select a runbook from the left to view detailed guidance.
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
