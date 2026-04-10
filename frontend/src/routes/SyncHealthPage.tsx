import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import DashboardState from '../components/DashboardState';
import SkeletonLoader from '../components/SkeletonLoader';
import { fetchSyncHealth, triggerResync, type SyncHealthResponse, type SyncHealthRow } from '../lib/phase2Api';
import { ApiError } from '../lib/apiClient';
import { formatAbsoluteTime, formatRelativeTime } from '../lib/format';
import { useToastStore } from '../stores/useToastStore';
import '../styles/phase2.css';
import '../styles/dashboard.css';
import '../styles/skeleton.css';

const SyncHealthPage = () => {
  const addToast = useToastStore((s) => s.addToast);
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [payload, setPayload] = useState<SyncHealthResponse | null>(null);
  const [error, setError] = useState<string>('Unable to load sync health.');
  const [syncingId, setSyncingId] = useState<string | null>(null);

  const load = useCallback(async (notify = false) => {
    setState('loading');
    setError('Unable to load sync health.');
    try {
      const data = await fetchSyncHealth();
      setPayload(data);
      setState('ready');
      if (notify) addToast('Re-sync triggered');
    } catch (err) {
      setState('error');
      setError(err instanceof Error ? err.message : 'Unable to load sync health.');
      if (notify) addToast('Re-sync failed', 'error');
    }
  }, [addToast]);

  const handleResync = useCallback(
    async (connectionId: string) => {
      if (!window.confirm('Trigger a re-sync for this connection?')) {
        return;
      }
      setSyncingId(connectionId);
      try {
        await triggerResync(connectionId);
        await load();
      } catch (err) {
        if (err instanceof ApiError && err.status === 501) {
          window.alert('Re-sync is not yet implemented for this connection type.');
        } else {
          window.alert(err instanceof Error ? err.message : 'Failed to trigger re-sync.');
        }
      } finally {
        setSyncingId(null);
      }
    },
    [load],
  );

  useEffect(() => {
    void load();
  }, [load]);

  const rows = useMemo<SyncHealthRow[]>(() => payload?.rows ?? [], [payload]);
  const generatedAt = payload?.generated_at ?? null;
  const [activeStatusFilter, setActiveStatusFilter] = useState<string>('all');
  const [activeProvider, setActiveProvider] = useState<string>('');

  const providers = useMemo(() => [...new Set(rows.map((r: SyncHealthRow) => r.provider).filter(Boolean))], [rows]);

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = { all: rows.length, fresh: 0, stale: 0, failed: 0 };
    for (const r of rows) {
      const s = r.state?.toLowerCase?.() ?? '';
      if (s in counts) counts[s]++;
    }
    return counts;
  }, [rows]);

  const filteredRows = useMemo(() => {
    return rows.filter((r: SyncHealthRow) => {
      if (activeStatusFilter !== 'all' && r.state?.toLowerCase() !== activeStatusFilter) return false;
      if (activeProvider && r.provider !== activeProvider) return false;
      return true;
    });
  }, [rows, activeStatusFilter, activeProvider]);

  const stateClass = useMemo(
    () => (value: string) => {
      const normalized = value.toLowerCase();
      return `phase2-pill phase2-pill--${normalized}`;
    },
    [],
  );

  if (state === 'loading') {
    return (
      <section className="phase2-page">
        <header className="phase2-page__header">
          <div>
            <p className="dashboardEyebrow">Operations</p>
            <h1 className="dashboardHeading">Sync Health</h1>
          </div>
        </header>
        <div className="phase2-grid">
          <SkeletonLoader variant="stat" count={4} />
        </div>
        <SkeletonLoader variant="table" />
      </section>
    );
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
        <button type="button" className="button secondary" onClick={() => void load(true)}>
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

      <div className="phase2-row-actions" style={{ marginBottom: '1rem', flexWrap: 'wrap' }}>
        {(['all', 'fresh', 'stale', 'failed'] as const).map((status) => (
          <button
            key={status}
            type="button"
            className={`button ${activeStatusFilter === status ? 'primary' : 'tertiary'}`}
            onClick={() => setActiveStatusFilter(status)}
          >
            {status.charAt(0).toUpperCase() + status.slice(1)} ({statusCounts[status] ?? 0})
          </button>
        ))}
        {providers.length > 1 ? (
          <select
            value={activeProvider}
            onChange={(e) => setActiveProvider(e.target.value)}
            className="phase2-input"
            style={{ maxWidth: 200 }}
          >
            <option value="">All providers</option>
            {providers.map((p: string) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        ) : null}
      </div>

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
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((row) => (
              <tr key={row.id}>
                <td>
                  <Link to={`/ops/sync-health/${row.id}`}>{row.name}</Link>
                </td>
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
                    disabled={syncingId !== null}
                    onClick={() => void handleResync(row.id)}
                  >
                    {syncingId === row.id ? 'Syncing…' : 'Re-sync'}
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
