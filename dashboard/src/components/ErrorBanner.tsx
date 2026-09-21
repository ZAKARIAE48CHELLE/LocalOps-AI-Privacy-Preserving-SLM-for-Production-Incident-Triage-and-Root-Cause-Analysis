import React from 'react';

interface ErrorBannerProps {
  message: string;
  onDismiss?: () => void;
}

export const ErrorBanner: React.FC<ErrorBannerProps> = ({ message, onDismiss }) => {
  if (!message) return null;

  return (
    <div className="error-banner">
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
        <span style={{ fontSize: '1.2rem' }}>⚠️</span>
        <div>
          <strong style={{ display: 'block', fontSize: '0.85rem' }}>Operational Error</strong>
          <span style={{ fontSize: '0.82rem', opacity: 0.9 }}>{message}</span>
        </div>
      </div>
      {onDismiss && (
        <button
          onClick={onDismiss}
          style={{
            background: 'transparent',
            border: 'none',
            color: '#fda4af',
            cursor: 'pointer',
            fontSize: '1rem',
            padding: '0.2rem',
          }}
          title="Dismiss alert"
        >
          ✕
        </button>
      )}
    </div>
  );
};
