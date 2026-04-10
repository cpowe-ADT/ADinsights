import { useCallback, useEffect, useState } from 'react';

import DashboardState from '../components/DashboardState';
import SkeletonLoader from '../components/SkeletonLoader';
import { API_BASE_URL } from '../lib/apiClient';
import { listAuditLogs, type AuditLogEntry } from '../lib/phase2Api';
import { formatAbsoluteTime, formatRelativeTime } from '../lib/format';
import '../styles/phase2.css';
import '../styles/dashboard.css';
import '../styles/skeleton.css';

const PAGE_SIZE = 20;

const AuditLogPage = () => {
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [rows, setRows] = useState<AuditLogEntry[]>([]);
  const [count, setCount] = useState(0);
  const [error, setError] = useState('Unable to load audit logs.');
  const [actionFilter, setActionFilter] = useState('');
  const [resourceFilter, setResourceFilter] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrevious, setHasPrevious] = useState(false);

  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));

  const load = useCallback(async () => {
    setState('loading');
    try {
      const response = await listAuditLogs({
        action: actionFilter.trim() || undefined,
        resource_type: resourceFilter.trim() || undefined,
        page,
        ...(startDate ? { start_date: startDate } : {}),
        ...(endDate ? { end_date: endDate } : {}),
      } as Parameters<typeof listAuditLogs>[0]);
      setRows(response.results);
      setCount(response.count);
      setHasNext(response.next !== null);
      setHasPrevious(response.previous !== null);
      setState('ready');
    } catch (err) {
      setState('error');
      setError(err instanceof Error ? err.message : 'Unable to load audit logs.');
    }
  }, [actionFilter, resourceFilter, startDate, endDate, page]);

  useEffect(() => {
    void load();
  }, [load]);

  // Reset to page 1 when filters change
  const handleFilterChange = useCallback(
    (setter: (val: string) => void) => (event: React.ChangeEvent<HTMLInputElement>) => {
      setter(event.target.value);
      setPage(1);
    },
    [],
  );

  const exportJson = useCallback(() => {
    const blob = new Blob([JSON.stringify(rows, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'audit-log-export.json';
    link.click();
    URL.revokeObjectURL(url);
  }, [rows]);

  const exportCsv = useCallback(() => {
    const params = new URLSearchParams();
    if (actionFilter.trim()) params.set('action', actionFilter.trim());
    if (resourceFilter.trim()) params.set('resource_type', resourceFilter.trim());
    const base = API_BASE_URL.replace(/\/$/, '');
    const url = `${base}/audit-logs/export_csv/?${params.toString()}`;
    window.open(url, '_blank');
  }, [actionFilter, resourceFilter]);

  if (state === 'loading') {
    return (
      <section className="phase2-page">
        <header className="phase2-page__header">
          <div>
            <p className="dashboardEyebrow">Operations</p>
            <h1 className="dashboardHeading">Audit Log</h1>
          </div>
        </header>
        <SkeletonLoader variant="table" />
      </section>
    );
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
          <p className="phase2-page__subhead">
            Tenant-scoped operational and security event history.
          </p>
        </div>
        <div className="phase2-row-actions">
          <button type="button" className="button secondary" onClick={() => void load()}>
            Refresh
          </button>
          <button
            type="button"
            className="button tertiary"
            onClick={exportCsv}
          >
            Export CSV
          </button>
          <button
            type="button"
            className="button tertiary"
            onClick={exportJson}
            disabled={rows.length === 0}
          >
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
            onChange={handleFilterChange(setActionFilter)}
            placeholder="e.g. report_created"
          />
        </label>
        <label className="phase2-form__field" htmlFor="audit-resource">
          <span>Resource filter</span>
          <input
            id="audit-resource"
            value={resourceFilter}
            onChange={handleFilterChange(setResourceFilter)}
            placeholder="e.g. report_definition"
          />
        </label>
        <label className="phase2-form__field" htmlFor="audit-start-date">
          <span>Start date</span>
          <input
            id="audit-start-date"
            type="date"
            className="phase2-input"
            value={startDate}
            onChange={handleFilterChange(setStartDate)}
          />
        </label>
        <label className="phase2-form__field" htmlFor="audit-end-date">
          <span>End date</span>
          <input
            id="audit-end-date"
            type="date"
            className="phase2-input"
            value={endDate}
            onChange={handleFilterChange(setEndDate)}
          />
        </label>
      </div>

      <p className="phase2-note">
        Showing {rows.length} of {count} events.
      </p>

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

      {count > 0 && (
        <div className="phase2-row-actions" style={{ justifyContent: 'center', marginTop: '1rem' }}>
          <button
            type="button"
            className="button secondary"
            disabled={!hasPrevious}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Previous
          </button>
          <span>
            Page {page} of {totalPages}
          </span>
          <button
            type="button"
            className="button secondary"
            disabled={!hasNext}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </button>
        </div>
      )}
    </section>
  );
};

export default AuditLogPage;
