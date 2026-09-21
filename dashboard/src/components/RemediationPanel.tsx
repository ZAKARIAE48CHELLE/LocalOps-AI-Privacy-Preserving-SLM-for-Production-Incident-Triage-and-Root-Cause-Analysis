import React from 'react';
import { RemediationRecommendation } from '../types/api';

interface RemediationPanelProps {
  remediation?: RemediationRecommendation | null;
}

export const RemediationPanel: React.FC<RemediationPanelProps> = ({ remediation }) => {
  if (!remediation) {
    return (
      <div
        className="glass-card"
        style={{
          borderColor: 'rgba(234, 179, 8, 0.3)',
          background: 'rgba(234, 179, 8, 0.05)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <span style={{ fontSize: '1.2rem' }}>ℹ️</span>
          <div>
            <div style={{ fontWeight: 600, color: 'var(--sev-p3-text)', fontSize: '0.9rem' }}>
              No Direct Runbook Grounding Found
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
              No operational runbook met the semantic similarity threshold for this incident pattern. Proceed with standard diagnostic procedures.
            </div>
          </div>
        </div>
      </div>
    );
  }

  const scorePercent = Math.round(remediation.relevance_score * 100);

  return (
    <div
      className="glass-card"
      style={{
        border: '1px solid rgba(16, 185, 129, 0.4)',
        background: 'rgba(16, 185, 129, 0.04)',
      }}
    >
      <div className="glass-card-header" style={{ borderBottom: '1px solid rgba(16, 185, 129, 0.2)', paddingBottom: '0.85rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
            <span
              style={{
                background: 'rgba(16, 185, 129, 0.2)',
                color: '#6ee7b7',
                border: '1px solid #10b981',
                padding: '0.15rem 0.5rem',
                borderRadius: '4px',
                fontSize: '0.72rem',
                fontWeight: 700,
                fontFamily: 'var(--font-mono)',
              }}
            >
              GROUNDED OPERATIONAL RUNBOOK
            </span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              (Retrieved via Hybrid BM25/Dense RAG)
            </span>
          </div>
          <h3 style={{ fontSize: '1.15rem', color: '#f8fafc', fontWeight: 600 }}>
            {remediation.runbook_title}
          </h3>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: '0.2rem' }}>
            Document: {remediation.runbook_document} | Section: {remediation.section}
          </div>
        </div>

        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Relevance Match</div>
          <div
            style={{
              fontSize: '1.4rem',
              fontWeight: 700,
              fontFamily: 'var(--font-mono)',
              color: '#34d399',
            }}
          >
            {scorePercent}%
          </div>
        </div>
      </div>

      {remediation.matched_keywords && remediation.matched_keywords.length > 0 && (
        <div style={{ marginTop: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>
            MATCHED SIGNALS:
          </span>
          {remediation.matched_keywords.map((kw, i) => (
            <span
              key={i}
              style={{
                background: 'rgba(56, 189, 248, 0.1)',
                border: '1px solid rgba(56, 189, 248, 0.25)',
                color: '#38bdf8',
                borderRadius: '4px',
                padding: '0.15rem 0.45rem',
                fontSize: '0.72rem',
                fontFamily: 'var(--font-mono)',
              }}
            >
              {kw}
            </span>
          ))}
        </div>
      )}

      <div style={{ marginTop: '1rem' }}>
        <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
          RECOMMENDED REMEDIATION & MITIGATION STEPS:
        </div>
        <div
          style={{
            background: 'var(--bg-inset)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            padding: '1rem',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.84rem',
            lineHeight: 1.6,
            color: '#e2e8f0',
            whiteSpace: 'pre-wrap',
          }}
        >
          {remediation.content}
        </div>
      </div>

      <div className="advisory-notice" style={{ marginTop: '0.85rem' }}>
        ⚠️ Verified runbook advice. Actions must be executed by authorized on-call engineers according to standard operational change controls.
      </div>
    </div>
  );
};
