import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import DashboardState from '../components/DashboardState';
import { fetchSyncHealth, triggerResync, type SyncHealthRow } from '../lib/phase2Api';
import { formatAbsoluteTime, formatRelativeTime } from '../lib/format';
import { useToastStore } from '../stores/useToastStore';
import '../styles/phase2.css';
import '../styles/dashboard.css';

const SyncConnectionDetailPage = () => {
  const { connectionId } = useParams<{ connectionId: string }>();
  const addToast = useToastStore((s) => s.addToast);

  const [state, setState] = useState<'loading' | 'ready' | 'error' | 'not-found'>('loading');
  const [connection, setConnection] = useState<SyncHealthRow | null>(null);
  const [error, setError] = useState<string>('Unable to load sync health.');
  const [resyncing, setResyncing] = useState(false);

  const load = useCallback(async () => {
    setState('loading');
    setError('Unable to load sync health.');
    try {
      const data = await fetchSyncHealth();
      const row = data.rows.find((r) => r.id === connectionId) ?? null;
      if (row) {
        setConnection(row);
        setState('ready');
      } else {
        setState('not-found');
      }
    } catch (err) {
      setState('error');
      setError(err instanceof Error ? err.message : 'Unable to load sync health.');
    }
  }, [connectionId]);

  useEffect(() => {
    void load();
  }, [load]);

  const stateClass = useMemo(
    () => (value: string) => `phase2-pill phase2-pill--${value.toLowerCase()}`,
    [],
  );

  const handleResync = useCallback(async () => {
    if (!connectionId) return;
    const confirmed = window.confirm(
      'Are you sure you want to trigger a re-sync for this connection?',
    );
    if (!confirmed) return;

    setResyncing(true);
    try {
      await triggerResync(connectionId);
      addToast('Re-sync triggered successfully.', 'success');
      void load();
    } catch (err) {
      addToast(
        err instanceof Error ? err.message : 'Failed to trigger re-sync.',
        { tone: 'error' },
      );
    } finally {
      setResyncing(false);
    }
  }, [connectionId, addToast, load]);

  if (state === 'loading') {
    return <DashboardState variant="loading" layout="page" message="Loading connection details..." />;
  }

  if (state === 'error') {
    return (
      <DashboardState
        variant="error"
        layout="page"
        title="Connection detail unavailable"
        message={error}
        actionLabel="Retry"
        onAction={() => void load()}
      />
    );
  }

  if (state === 'not-found' || !connection) {
    return (
      <DashboardState
        variant="empty"
        layout="page"
        title="Connection not found"
        message={`No sync connection found with ID "${connectionId ?? ''}".`}
      />
    );
  }

  return (
    <section className="phase2-page">
      <header className="phase2-page__header">
        <div>
          <p className="dashboardEyebrow">Operations</p>
          <h1 className="dashboardHeading">{connection.name}</h1>
          <p className="phase2-page__subhead">Sync connection detail view.</p>
        </div>
        <div className="phase2-row-actions">
          <Link to="/ops/sync-health" className="button tertiary">
            Back to Sync Health
          </Link>
          <button
            type="button"
            className="button secondary"
            disabled={resyncing}
            onClick={() => void handleResync()}
          >
            {resyncing ? 'Re-syncing...' : 'Re-sync'}
          </button>
        </div>
      </header>

      <article className="phase2-card" style={{ marginTop: '1rem' }}>
        <table className="phase2-table">
          <tbody>
            <tr>
              <th>Name</th>
              <td>{connection.name}</td>
            </tr>
            <tr>
              <th>Provider</th>
              <td>{connection.provider ?? 'Unknown'}</td>
            </tr>
            <tr>
              <th>Schedule type</th>
              <td>{connection.schedule_type}</td>
            </tr>
            <tr>
              <th>Active</th>
              <td>{connection.is_active ? 'Yes' : 'No'}</td>
            </tr>
            <tr>
              <th>State</th>
              <td>
                <span className={stateClass(connection.state)}>{connection.state}</span>
              </td>
            </tr>
            <tr>
              <th>Last synced</th>
              <td>
                {connection.last_synced_at
                  ? `${formatRelativeTime(connection.last_synced_at)} (${formatAbsoluteTime(connection.last_synced_at)})`
                  : 'Never'}
              </td>
            </tr>
            <tr>
              <th>Last job status</th>
              <td>{connection.last_job_status ?? 'N/A'}</td>
            </tr>
            <tr>
              <th>Last job error</th>
              <td>{connection.last_job_error ?? 'None'}</td>
            </tr>
          </tbody>
        </table>
      </article>
    </section>
  );
};

export default SyncConnectionDetailPage;
