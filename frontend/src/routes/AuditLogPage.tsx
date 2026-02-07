import { useCallback, useEffect, useState } from 'react';

import DashboardState from '../components/DashboardState';
import { listAuditLogs, type AuditLogEntry } from '../lib/phase2Api';
import { formatAbsoluteTime, formatRelativeTime } from '../lib/format';
import '../styles/phase2.css';
import '../styles/dashboard.css';

const AuditLogPage = () => {
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [rows, setRows] = useState<AuditLogEntry[]>([]);
  const [count, setCount] = useState(0);
  const [error, setError] = useState('Unable to load audit logs.');
  const [actionFilter, setActionFilter] = useState('');
  const [resourceFilter, setResourceFilter] = useState('');

  const load = useCallback(async () => {
    setState('loading');
    try {
      const response = await listAuditLogs({
        action: actionFilter.trim() || undefined,
        resource_type: resourceFilter.trim() || undefined,
      });
      setRows(response.results);
      setCount(response.count);
      setState('ready');
    } catch (err) {
      setState('error');
      setError(err instanceof Error ? err.message : 'Unable to load audit logs.');
    }
  }, [actionFilter, resourceFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  const exportJson = useCallback(() => {
    const blob = new Blob([JSON.stringify(rows, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'audit-log-export.json';
    link.click();
    URL.revokeObjectURL(url);
  }, [rows]);

  if (state === 'loading') {
    return <DashboardState variant="loading" layout="page" message="Loading audit logs…" />;
  }

  if (state === 'error') {
    return (
      <DashboardState
        variant="error"
        layout="page"
        title="Audit logs unavailable"
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
          <h1 className="dashboardHeading">Audit Log</h1>
          <p className="phase2-page__subhead">Tenant-scoped operational and security event history.</p>
        </div>
        <div className="phase2-row-actions">
          <button type="button" className="button secondary" onClick={() => void load()}>
            Refresh
          </button>
          <button type="button" className="button tertiary" onClick={exportJson} disabled={rows.length === 0}>
            Export JSON
          </button>
        </div>
      </header>

      <div className="phase2-toolbar">
        <label className="phase2-form__field" htmlFor="audit-action">
          <span>Action filter</span>
          <input
            id="audit-action"
            value={actionFilter}
            onChange={(event) => setActionFilter(event.target.value)}
            placeholder="e.g. report_created"
          />
        </label>
        <label className="phase2-form__field" htmlFor="audit-resource">
          <span>Resource filter</span>
          <input
            id="audit-resource"
            value={resourceFilter}
            onChange={(event) => setResourceFilter(event.target.value)}
            placeholder="e.g. report_definition"
          />
        </label>
      </div>

      <p className="phase2-note">Showing {rows.length} of {count} events.</p>

      {rows.length === 0 ? (
        <DashboardState
          variant="empty"
          layout="page"
          title="No audit events"
          message="No events matched the current filters."
        />
      ) : (
        <table className="phase2-table">
          <thead>
            <tr>
              <th>Action</th>
              <th>Resource</th>
              <th>Actor</th>
              <th>Timestamp</th>
              <th>Metadata</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.action}</td>
                <td>
                  {row.resource_type}
                  <div className="phase2-note">{row.resource_id}</div>
                </td>
                <td>{row.user?.email ?? 'System'}</td>
                <td>
                  {formatRelativeTime(row.created_at)} ({formatAbsoluteTime(row.created_at)})
                </td>
                <td>
                  <pre className="phase2-json">{JSON.stringify(row.metadata, null, 2)}</pre>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
};

export default AuditLogPage;
