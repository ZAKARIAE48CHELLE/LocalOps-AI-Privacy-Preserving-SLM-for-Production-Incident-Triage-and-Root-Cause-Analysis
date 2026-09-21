import React from 'react';
import { Severity, IncidentType } from '../types/api';

interface SeverityBadgeProps {
  severity: Severity | string;
}

export const SeverityBadge: React.FC<SeverityBadgeProps> = ({ severity }) => {
  const normSev = severity || 'P4_LOW';
  const label = normSev.replace('_', ' ');

  return (
    <span className={`badge-severity badge-${normSev}`}>
      <span className="pulse-dot warning" style={{ width: '6px', height: '6px' }} />
      {label}
    </span>
  );
};

interface IncidentTypeBadgeProps {
  type: IncidentType | string;
}

export const IncidentTypeBadge: React.FC<IncidentTypeBadgeProps> = ({ type }) => {
  return (
    <span className="badge-type">
      {type || 'UNKNOWN'}
    </span>
  );
};

interface StatusDotProps {
  status: 'online' | 'offline' | 'warning';
  label?: string;
}

export const StatusDot: React.FC<StatusDotProps> = ({ status, label }) => {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.45rem', fontSize: '0.8rem' }}>
      <span className={`pulse-dot ${status}`} />
      {label && <span style={{ color: 'var(--text-secondary)' }}>{label}</span>}
    </span>
  );
};
