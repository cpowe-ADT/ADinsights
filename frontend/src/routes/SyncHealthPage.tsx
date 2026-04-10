import { useCallback, useEffect, useMemo, useState } from 'react';

import DashboardState from '../components/DashboardState';
import { fetchSyncHealth, triggerSync, type SyncHealthResponse } from '../lib/phase2Api';
import { formatAbsoluteTime, formatRelativeTime } from '../lib/format';
import '../styles/phase2.css';
import '../styles/dashboard.css';

const SyncHealthPage = () => {
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [payload, setPayload] = useState<SyncHealthResponse | null>(null);
  const [error, setError] = useState<string>('Unable to load sync health.');
  const [stateFilter, setStateFilter] = useState<string>('all');
  const [triggeringId, setTriggeringId] = useState<string | null>(null);

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

  const filteredRows = useMemo(
    () => stateFilter === 'all' ? rows : rows.filter((r) => r.state === stateFilter),
    [rows, stateFilter],
  );

  const stateClass = useMemo(
    () => (value: string) => {
      const normalized = value.toLowerCase();
      return `phase2-pill phase2-pill--${normalized}`;
    },
    [],
  );

  const handleTriggerSync = useCallback(async (connectionId: string) => {
    setTriggeringId(connectionId);
    try {
      await triggerSync(connectionId);
      // Show inline success — reload data
      await load();
    } catch {
      // 501 is expected (stub) — still show the attempt
    } finally {
      setTriggeringId(null);
    }
  }, [load]);

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

      <div className="phase2-toolbar" role="group" aria-label="State filter">
        {['all', 'fresh', 'stale', 'failed', 'missing', 'inactive'].map((filter) => (
          <button
            key={filter}
            type="button"
            className={`button ${stateFilter === filter ? 'primary' : 'secondary'}`}
            onClick={() => setStateFilter(filter)}
          >
            {filter === 'all' ? 'All' : `${filter.charAt(0).toUpperCase()}${filter.slice(1)}`}
            {filter !== 'all' && payload?.counts ? ` (${payload.counts[filter as keyof typeof payload.counts] ?? 0})` : ''}
          </button>
        ))}
      </div>

      <div className="phase2-row-actions" style={{ marginBottom: '1rem' }}>
        <p className="phase2-note">
          Last refreshed: {generatedAt ? formatRelativeTime(generatedAt) : 'Never'}
        </p>
        <button type="button" className="button secondary" onClick={() => void load()}>
          Refresh
        </button>
      </div>

      {filteredRows.length === 0 ? (
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
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((row) => (
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
                <td>
                  <button
                    type="button"
                    className="button tertiary"
                    onClick={() => void handleTriggerSync(row.id)}
                    disabled={triggeringId === row.id}
                  >
                    {triggeringId === row.id ? 'Triggering\u2026' : 'Re-sync'}
                  </button>
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
