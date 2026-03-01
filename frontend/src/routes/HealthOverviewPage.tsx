import { useCallback, useEffect, useState } from 'react';

import DashboardState from '../components/DashboardState';
import { fetchHealthOverview, type HealthOverviewResponse } from '../lib/phase2Api';
import { formatAbsoluteTime, formatRelativeTime } from '../lib/format';
import '../styles/phase2.css';
import '../styles/dashboard.css';

const HealthOverviewPage = () => {
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [payload, setPayload] = useState<HealthOverviewResponse | null>(null);
  const [error, setError] = useState<string>('Unable to load health overview.');

  const load = useCallback(async () => {
    setState('loading');
    try {
      const data = await fetchHealthOverview();
      setPayload(data);
      setState('ready');
    } catch (err) {
      setState('error');
      setError(err instanceof Error ? err.message : 'Unable to load health overview.');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (state === 'loading') {
    return <DashboardState variant="loading" layout="page" message="Loading health overview…" />;
  }

  if (state === 'error') {
    return (
      <DashboardState
        variant="error"
        layout="page"
        title="Health overview unavailable"
        message={error}
        actionLabel="Retry"
        onAction={() => void load()}
      />
    );
  }

  const cards = payload?.cards ?? [];
  const generatedAt = payload?.generated_at;
  const overallStatus = payload?.overall_status ?? 'ok';

  return (
    <section className="phase2-page">
      <header className="phase2-page__header">
        <div>
          <p className="dashboardEyebrow">Operations</p>
          <h1 className="dashboardHeading">Health Overview</h1>
          <p className="phase2-page__subhead">
            Unified status for API, Airbyte, dbt, and timezone checks.
          </p>
        </div>
        <div className="phase2-row-actions">
          <span className={`phase2-pill phase2-pill--${overallStatus}`}>{overallStatus}</span>
          <button type="button" className="button secondary" onClick={() => void load()}>
            Refresh
          </button>
        </div>
      </header>

      {generatedAt ? (
        <p className="phase2-note">
          Updated {formatRelativeTime(generatedAt)} ({formatAbsoluteTime(generatedAt)})
        </p>
      ) : null}

      {cards.length === 0 ? (
        <DashboardState
          variant="empty"
          layout="page"
          title="No health cards"
          message="Health services have not reported data yet."
        />
      ) : (
        <div className="phase2-grid">
          {cards.map((card) => (
            <article key={card.key} className="phase2-card">
              <div className="phase2-row-actions">
                <h3>{card.key.toUpperCase()}</h3>
                <span className={`phase2-pill phase2-pill--${card.status}`}>{card.status}</span>
              </div>
              <p>HTTP status: {card.http_status}</p>
              <p>{card.detail ?? 'No additional details provided.'}</p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
};

export default HealthOverviewPage;
