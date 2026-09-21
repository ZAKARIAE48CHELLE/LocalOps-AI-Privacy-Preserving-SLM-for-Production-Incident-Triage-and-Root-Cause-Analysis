import React from 'react';

interface TelemetryCardProps {
  label: string;
  value: string | number;
  subtext?: string;
  highlight?: boolean;
  color?: string;
  icon?: string;
}

export const TelemetryCard: React.FC<TelemetryCardProps> = ({
  label,
  value,
  subtext,
  highlight = false,
  color,
  icon,
}) => {
  return (
    <div
      className="stat-card"
      style={{
        borderColor: highlight ? 'var(--border-glow)' : undefined,
        boxShadow: highlight ? 'var(--shadow-glow)' : undefined,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span className="stat-label">{label}</span>
        {icon && <span style={{ fontSize: '1.1rem', opacity: 0.8 }}>{icon}</span>}
      </div>
      <div
        className="stat-value"
        style={{ color: color || 'var(--text-primary)' }}
      >
        {value}
      </div>
      {subtext && <div className="stat-subtext">{subtext}</div>}
    </div>
  );
};
