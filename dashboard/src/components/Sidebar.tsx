import React from 'react';

export type NavTab = 'overview' | 'triage' | 'batch' | 'monitoring' | 'runbooks' | 'system';

interface SidebarProps {
  currentTab: NavTab;
  onTabChange: (tab: NavTab) => void;
  serviceReady: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onTabChange,
  serviceReady,
}) => {
  const navItems: Array<{ id: NavTab; label: string; icon: string }> = [
    { id: 'overview', label: 'Mission Control', icon: '🛰️' },
    { id: 'triage', label: 'Incident Triage', icon: '⚡' },
    { id: 'batch', label: 'Batch Analysis', icon: '📦' },
    { id: 'monitoring', label: 'Telemetry & GPU', icon: '📊' },
    { id: 'runbooks', label: 'Runbook Browser', icon: '📖' },
    { id: 'system', label: 'System Specs', icon: '⚙️' },
  ];

  return (
    <aside className="sidebar">
      <div className="brand-badge">
        <div className="brand-logo-icon">
          <span style={{ fontSize: '1.25rem' }}>🛡️</span>
        </div>
        <div>
          <div className="brand-title">LocalOps AI</div>
          <div className="brand-subtitle">Privacy-Preserving SLM</div>
        </div>
      </div>

      <nav style={{ flex: 1 }}>
        <ul className="nav-list">
          {navItems.map((item) => (
            <li key={item.id}>
              <button
                className={`nav-item-btn ${currentTab === item.id ? 'active' : ''}`}
                onClick={() => onTabChange(item.id)}
              >
                <span className="nav-icon">{item.icon}</span>
                <span>{item.label}</span>
              </button>
            </li>
          ))}
        </ul>
      </nav>

      <div className="sidebar-footer">
        <div className="privacy-shield-tag">
          <span>🔒</span>
          <span>Zero Cloud Exfiltration</span>
        </div>
        <div>In-Memory Client State</div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.2rem' }}>
          <span>Service Status</span>
          <span style={{ color: serviceReady ? 'var(--accent-emerald)' : 'var(--accent-amber)', fontWeight: 600 }}>
            {serviceReady ? 'ONLINE' : 'CONNECTING'}
          </span>
        </div>
      </div>
    </aside>
  );
};
