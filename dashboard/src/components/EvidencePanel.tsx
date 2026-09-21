import React, { useState } from 'react';
import { copyToClipboard } from '../utils/export';

interface EvidencePanelProps {
  evidence: string[];
}

export const EvidencePanel: React.FC<EvidencePanelProps> = ({ evidence }) => {
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const handleCopy = async (text: string, idx: number) => {
    const ok = await copyToClipboard(text);
    if (ok) {
      setCopiedIndex(idx);
      setTimeout(() => setCopiedIndex(null), 2000);
    }
  };

  if (!evidence || evidence.length === 0) {
    return (
      <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', fontStyle: 'italic' }}>
        No supporting evidence excerpts extracted.
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      {evidence.map((item, idx) => (
        <div
          key={idx}
          style={{
            position: 'relative',
            background: 'var(--bg-inset)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            padding: '0.85rem 1rem',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '0.4rem',
              fontSize: '0.75rem',
              color: 'var(--text-muted)',
              fontFamily: 'var(--font-mono)',
            }}
          >
            <span>EVIDENCE #{idx + 1}</span>
            <button
              onClick={() => handleCopy(item, idx)}
              className="btn btn-secondary btn-sm"
              style={{ padding: '0.2rem 0.5rem', fontSize: '0.72rem' }}
              title="Copy evidence excerpt"
            >
              {copiedIndex === idx ? '✓ Copied' : 'Copy'}
            </button>
          </div>
          <pre
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.82rem',
              color: '#38bdf8',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-all',
              margin: 0,
            }}
          >
            {item}
          </pre>
        </div>
      ))}
    </div>
  );
};
