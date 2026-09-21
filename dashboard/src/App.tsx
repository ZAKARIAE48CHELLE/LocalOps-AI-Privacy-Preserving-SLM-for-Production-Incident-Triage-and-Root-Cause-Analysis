import React, { useState, useEffect } from 'react';
import {
  HealthResponse,
  ReadinessResponse,
  ModelInfoResponse,
  LiveTelemetrySummary,
} from './types/api';
import localopsClient from './api/localopsClient';
import { Sidebar, NavTab } from './components/Sidebar';
import { Header } from './components/Header';
import { OverviewPage } from './pages/OverviewPage';
import { TriagePage } from './pages/TriagePage';
import { BatchPage } from './pages/BatchPage';
import { MonitoringPage } from './pages/MonitoringPage';
import { RunbooksPage } from './pages/RunbooksPage';
import { SystemPage } from './pages/SystemPage';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<NavTab>('overview');
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [readiness, setReadiness] = useState<ReadinessResponse | null>(null);
  const [modelInfo, setModelInfo] = useState<ModelInfoResponse | null>(null);
  const [telemetry, setTelemetry] = useState<LiveTelemetrySummary | null>(null);

  // Poll system health and live telemetry every 3 seconds
  useEffect(() => {
    let isMounted = true;

    const pollStatus = async () => {
      try {
        const [h, r, t] = await Promise.all([
          localopsClient.getHealth().catch(() => null),
          localopsClient.getReadiness().catch(() => null),
          localopsClient.getLiveTelemetry().catch(() => null),
        ]);

        if (isMounted) {
          if (h) setHealth(h);
          if (r) setReadiness(r);
          if (t) setTelemetry(t);
        }
      } catch {
        // Polling error handled gracefully
      }
    };

    // Initial fetch of static model info
    localopsClient.getModelInfo()
      .then((info) => {
        if (isMounted) setModelInfo(info);
      })
      .catch(() => {});

    pollStatus();
    const interval = setInterval(pollStatus, 3000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const getPageTitle = (tab: NavTab) => {
    switch (tab) {
      case 'overview':
        return { title: 'Mission Control', subtitle: 'Real-time operational health, model readiness, and cluster metrics' };
      case 'triage':
        return { title: 'Incident Triage', subtitle: 'Interactive SLM log diagnosis with grounded runbook remediation' };
      case 'batch':
        return { title: 'Batch Incident Analysis', subtitle: 'Multi-log evaluation with micro-batching and isolated error handling' };
      case 'monitoring':
        return { title: 'Telemetry & Monitoring', subtitle: 'Hardware telemetry, inference percentiles, and Prometheus metrics' };
      case 'runbooks':
        return { title: 'Runbook Browser', subtitle: 'Searchable index of pre-grounded operational playbooks' };
      case 'system':
        return { title: 'System Architecture', subtitle: 'Hardware specs, model parameters, and local privacy guarantees' };
    }
  };

  const { title, subtitle } = getPageTitle(currentTab);

  return (
    <div className="app-container">
      <Sidebar
        currentTab={currentTab}
        onTabChange={setCurrentTab}
        serviceReady={readiness?.ready ?? false}
      />

      <div className="content-area">
        <Header
          title={title}
          subtitle={subtitle}
          readiness={readiness}
          telemetry={telemetry}
        />

        <main style={{ flex: 1 }}>
          {currentTab === 'overview' && (
            <OverviewPage
              health={health}
              readiness={readiness}
              modelInfo={modelInfo}
              telemetry={telemetry}
              onNavigate={(tab) => setCurrentTab(tab)}
            />
          )}

          {currentTab === 'triage' && <TriagePage />}

          {currentTab === 'batch' && <BatchPage />}

          {currentTab === 'monitoring' && <MonitoringPage telemetry={telemetry} />}

          {currentTab === 'runbooks' && <RunbooksPage />}

          {currentTab === 'system' && (
            <SystemPage
              modelInfo={modelInfo}
              readiness={readiness}
              telemetry={telemetry}
            />
          )}
        </main>
      </div>
    </div>
  );
};

export default App;
