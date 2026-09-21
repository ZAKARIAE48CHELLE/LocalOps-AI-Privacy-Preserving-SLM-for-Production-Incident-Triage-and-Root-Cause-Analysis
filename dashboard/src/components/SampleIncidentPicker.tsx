import React from 'react';
import { SAMPLE_INCIDENTS, SampleIncident } from '../utils/sampleIncidents';

interface SampleIncidentPickerProps {
  onSelect: (sample: SampleIncident) => void;
  disabled?: boolean;
}

export const SampleIncidentPicker: React.FC<SampleIncidentPickerProps> = ({
  onSelect,
  disabled = false,
}) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
      <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 600 }}>
        LOAD SYNTHETIC INCIDENT BENCHMARK SAMPLE:
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
        {SAMPLE_INCIDENTS.map((sample) => (
          <button
            key={sample.id}
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => onSelect(sample)}
            disabled={disabled}
            style={{
              fontSize: '0.75rem',
              padding: '0.3rem 0.6rem',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem',
            }}
          >
            <span
              style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                background:
                  sample.category === 'DATABASE'
                    ? 'var(--type-db)'
                    : sample.category === 'INFRASTRUCTURE'
                    ? 'var(--type-infra)'
                    : sample.category === 'APPLICATION'
                    ? 'var(--type-app)'
                    : sample.category === 'SECURITY'
                    ? 'var(--type-sec)'
                    : sample.category === 'NETWORK'
                    ? 'var(--type-net)'
                    : 'var(--type-msg)',
              }}
            />
            {sample.name}
          </button>
        ))}
      </div>
    </div>
  );
};
