import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import DashboardState from '../components/DashboardState';
import SkeletonLoader from '../components/SkeletonLoader';
import { listAlertRuns, type AlertRun } from '../lib/phase2Api';
import { formatAbsoluteTime, formatRelativeTime } from '../lib/format';
import '../styles/phase2.css';
import '../styles/dashboard.css';
import '../styles/skeleton.css';

type StatusFilter = '' | 'success' | 'no_results' | 'partial' | 'failed' | 'started';

const STATUS_FILTERS: { label: string; value: StatusFilter }[] = [
  { label: 'All', value: '' },
  { label: 'Success', value: 'success' },
  { label: 'No Results', value: 'no_results' },
  { label: 'Partial', value: 'partial' },
  { label: 'Failed', value: 'failed' },
  { label: 'Started', value: 'started' },
];

const STATUS_PILL_CLASS: Record<string, string> = {
  success: 'fresh',
  failed: 'failed',
  started: 'info',
  no_results: 'inactive',
  partial: 'warning',
};

function formatDuration(ms: number): string {
  if (ms < 1000) {
    return `${ms}ms`;
  }
  return `${(ms / 1000).toFixed(1)}s`;
}

function truncate(text: string, maxLength: number): string {
  if (!text || text.length <= maxLength) {
    return text ?? '';
  }
  return text.slice(0, maxLength) + '...';
}

const AlertRunsPage = () => {
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [runs, setRuns] = useState<AlertRun[]>([]);
  const [count, setCount] = useState(0);
  const [error, setError] = useState('Unable to load alert history.');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('');

  const load = useCallback(async () => {
    setState('loading');
    try {
      const response = await listAlertRuns({
        status: statusFilter || undefined,
      });
      setRuns(response.results);
      setCount(response.count);
      setState('ready');
    } catch (err) {
      setState('error');
      setError(err instanceof Error ? err.message : 'Unable to load alert history.');
    }
  }, [statusFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  if (state === 'loading') {
    return (
      <section className="phase2-page">
        <header className="phase2-page__header">
          <div>
            <p className="dashboardEyebrow">Alerts</p>
            <h1 className="dashboardHeading">Alert History</h1>
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
        title="Alert history unavailable"
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
          <p className="dashboardEyebrow">Alerts</p>
          <h1 className="dashboardHeading">Alert History</h1>
          <p className="phase2-page__subhead">
            Timeline of triggered alert evaluations and their outcomes.
          </p>
        </div>
        <div className="phase2-page__actions">
          <Link to="/alerts" className="button tertiary">
            Back to alerts
          </Link>
          <button type="button" className="button secondary" onClick={() => void load()}>
            Refresh
          </button>
        </div>
      </header>

      <div className="phase2-filter-bar" role="group" aria-label="Filter by status">
        {STATUS_FILTERS.map((filter) => (
          <button
            key={filter.value}
            type="button"
            className={`button ${statusFilter === filter.value ? 'primary' : 'tertiary'}`}
            onClick={() => setStatusFilter(filter.value)}
          >
            {filter.label}
          </button>
        ))}
      </div>

      {runs.length === 0 ? (
        <DashboardState
          variant="empty"
          layout="page"
          title="No alert runs"
          message={
            statusFilter
              ? 'No runs match the selected filter. Try a different status.'
              : 'No alert evaluations have been recorded yet.'
          }
        />
      ) : (
        <>
          <p className="phase2-table__count">
            Showing {runs.length} of {count} runs
          </p>
          <table className="phase2-table">
            <thead>
              <tr>
                <th>Rule</th>
                <th>Status</th>
                <th>Rows</th>
                <th>Duration</th>
                <th>Summary</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => {
                const pillClass = STATUS_PILL_CLASS[run.status] ?? 'info';
                return (
                  <tr key={run.id}>
                    <td>{run.rule_name ?? run.rule_slug}</td>
                    <td>
                      <span className={`phase2-pill phase2-pill--${pillClass}`}>
                        {run.status.replace('_', ' ')}
                      </span>
                    </td>
                    <td>{run.row_count}</td>
                    <td>{formatDuration(run.duration_ms)}</td>
                    <td>
                      <span>{truncate(run.llm_summary, 80)}</span>
                      {run.error_message ? (
                        <span className="phase2-error-note">{run.error_message}</span>
                      ) : null}
                    </td>
                    <td>
                      {formatRelativeTime(run.created_at)} ({formatAbsoluteTime(run.created_at)})
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
};

export default AlertRunsPage;
