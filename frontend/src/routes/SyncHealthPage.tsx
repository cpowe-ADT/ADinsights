import { useCallback, useEffect, useMemo, useState } from 'react';

import DashboardState from '../components/DashboardState';
import { fetchSyncHealth, type SyncHealthResponse } from '../lib/phase2Api';
import { formatAbsoluteTime, formatRelativeTime } from '../lib/format';
import '../styles/phase2.css';
import '../styles/dashboard.css';

const SyncHealthPage = () => {
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [payload, setPayload] = useState<SyncHealthResponse | null>(null);
  const [error, setError] = useState<string>('Unable to load sync health.');

  const load = useCallback(async () => {
    setState('loading');
    setError('Unable to load sync health.');
    try {
      const data = await fetchSyncHealth();
      setPayload(data);
      setState('ready');
    } catch (err) {
      setState('error');
      setError(err instanceof Error ? err.message : 'Unable to load sync health.');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const rows = payload?.rows ?? [];
  const generatedAt = payload?.generated_at ?? null;

  const stateClass = useMemo(
    () => (value: string) => {
      const normalized = value.toLowerCase();
      return `phase2-pill phase2-pill--${normalized}`;
    },
    [],
  );

  if (state === 'loading') {
    return <DashboardState variant="loading" layout="page" message="Loading sync health…" />;
  }

  if (state === 'error') {
    return (
      <DashboardState
        variant="error"
        layout="page"
        title="Sync health unavailable"
        message={error}
        actionLabel="Retry"
        onAction={() => void load()}
      />
    );
  }

  return (
    <section className="phase2-page">
      <header className="phase2-page__header">
        <div>
          <p className="dashboardEyebrow">Operations</p>
          <h1 className="dashboardHeading">Sync Health</h1>
          <p className="phase2-page__subhead">
            Real-time tenant sync posture for connected Airbyte jobs.
          </p>
        </div>
        <button type="button" className="button secondary" onClick={() => void load()}>
          Refresh
        </button>
      </header>

      <div className="phase2-grid">
        <article className="phase2-stat">
          <p className="phase2-stat__label">Total connections</p>
          <p className="phase2-stat__value">{payload?.counts.total ?? 0}</p>
        </article>
        <article className="phase2-stat">
          <p className="phase2-stat__label">Fresh</p>
          <p className="phase2-stat__value">{payload?.counts.fresh ?? 0}</p>
        </article>
        <article className="phase2-stat">
          <p className="phase2-stat__label">Stale</p>
          <p className="phase2-stat__value">{payload?.counts.stale ?? 0}</p>
        </article>
        <article className="phase2-stat">
          <p className="phase2-stat__label">Failed</p>
          <p className="phase2-stat__value">{payload?.counts.failed ?? 0}</p>
        </article>
      </div>

      {generatedAt ? (
        <p className="phase2-note">
          Updated {formatRelativeTime(generatedAt)} ({formatAbsoluteTime(generatedAt)})
        </p>
      ) : null}

      {rows.length === 0 ? (
        <DashboardState
          variant="empty"
          layout="page"
          title="No sync connections"
          message="Create and activate Airbyte connections to populate this view."
        />
      ) : (
        <table className="phase2-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Provider</th>
              <th>Status</th>
              <th>Last sync</th>
              <th>Last job</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.name}</td>
                <td>{row.provider ?? 'Unknown'}</td>
                <td>
                  <span className={stateClass(row.state)}>{row.state}</span>
                </td>
                <td>
                  {row.last_synced_at
                    ? `${formatRelativeTime(row.last_synced_at)} (${formatAbsoluteTime(
                        row.last_synced_at,
                      )})`
                    : 'Never'}
                </td>
                <td>
                  {row.last_job_status ?? 'N/A'}
                  {row.last_job_error ? <div>{row.last_job_error}</div> : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
};

export default SyncHealthPage;
