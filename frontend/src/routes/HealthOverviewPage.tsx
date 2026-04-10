import { useCallback, useEffect, useRef, useState } from 'react';

import DashboardState from '../components/DashboardState';
import SkeletonLoader from '../components/SkeletonLoader';
import { fetchHealthOverview, type HealthOverviewResponse } from '../lib/phase2Api';
import { formatAbsoluteTime, formatRelativeTime } from '../lib/format';
import '../styles/phase2.css';
import '../styles/dashboard.css';
import '../styles/skeleton.css';

const AUTO_REFRESH_MS = 30_000;

const HealthOverviewPage = () => {
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [payload, setPayload] = useState<HealthOverviewResponse | null>(null);
  const [error, setError] = useState<string>('Unable to load health overview.');
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [autoRefreshing, setAutoRefreshing] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async (isAutoRefresh = false) => {
    if (!isAutoRefresh) {
      setState('loading');
    }
    if (isAutoRefresh) {
      setAutoRefreshing(true);
    }
    try {
      const data = await fetchHealthOverview();
      setPayload(data);
      setState('ready');
      setLastRefresh(new Date());
    } catch (err) {
      if (!isAutoRefresh) {
        setState('error');
      }
      setError(err instanceof Error ? err.message : 'Unable to load health overview.');
    } finally {
      setAutoRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load(false);
  }, [load]);

  useEffect(() => {
    intervalRef.current = setInterval(() => {
      void load(true);
    }, AUTO_REFRESH_MS);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [load]);

  if (state === 'loading') {
    return (
      <section className="phase2-page">
        <header className="phase2-page__header">
          <div>
            <p className="dashboardEyebrow">Operations</p>
            <h1 className="dashboardHeading">Health Overview</h1>
          </div>
        </header>
        <SkeletonLoader variant="card" count={4} />
      </section>
    );
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
          {autoRefreshing && (
            <span className="phase2-note" style={{ fontSize: '0.8rem', opacity: 0.7 }}>
              Refreshing...
            </span>
          )}
          <button type="button" className="button secondary" onClick={() => void load(false)}>
            Refresh
          </button>
        </div>
      </header>

      {generatedAt ? (
        <p className="phase2-note">
          Updated {formatRelativeTime(generatedAt)} ({formatAbsoluteTime(generatedAt)})
        </p>
      ) : null}

      {lastRefresh ? (
        <p className="phase2-note" data-testid="last-refresh">
          Last refreshed at {lastRefresh.toLocaleTimeString()} (auto-refresh every 30s)
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
