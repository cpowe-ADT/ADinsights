import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import DashboardState from '../components/DashboardState';
import { listSummaries, refreshSummary, type AISummary } from '../lib/phase2Api';
import { formatAbsoluteTime, formatRelativeTime } from '../lib/format';
import '../styles/phase2.css';
import '../styles/dashboard.css';

const SummariesPage = () => {
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [summaries, setSummaries] = useState<AISummary[]>([]);
  const [error, setError] = useState('Unable to load summaries.');
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setState('loading');
    try {
      const data = await listSummaries();
      setSummaries(data);
      setState('ready');
    } catch (err) {
      setState('error');
      setError(err instanceof Error ? err.message : 'Unable to load summaries.');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleRefreshSummary = useCallback(async () => {
    setRefreshing(true);
    try {
      await refreshSummary();
      await load();
    } finally {
      setRefreshing(false);
    }
  }, [load]);

  if (state === 'loading') {
    return <DashboardState variant="loading" layout="page" message="Loading summaries…" />;
  }

  if (state === 'error') {
    return (
      <DashboardState
        variant="error"
        layout="page"
        title="Summaries unavailable"
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
          <p className="dashboardEyebrow">AI Summaries</p>
          <h1 className="dashboardHeading">Summaries</h1>
          <p className="phase2-page__subhead">Review generated summaries and fallback behavior.</p>
        </div>
        <div className="phase2-row-actions">
          <button type="button" className="button secondary" onClick={() => void load()}>
            Refresh list
          </button>
          <button
            type="button"
            className="button primary"
            onClick={() => void handleRefreshSummary()}
            disabled={refreshing}
          >
            {refreshing ? 'Generating…' : 'Generate new summary'}
          </button>
        </div>
      </header>

      {summaries.length === 0 ? (
        <DashboardState
          variant="empty"
          layout="page"
          title="No summaries yet"
          message="Generate a summary to seed this timeline."
        />
      ) : (
        <table className="phase2-table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Status</th>
              <th>Source</th>
              <th>Generated</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {summaries.map((summary) => (
              <tr key={summary.id}>
                <td>{summary.title}</td>
                <td>
                  <span className={`phase2-pill phase2-pill--${summary.status}`}>
                    {summary.status}
                  </span>
                </td>
                <td>{summary.source}</td>
                <td>
                  {formatRelativeTime(summary.generated_at)} (
                  {formatAbsoluteTime(summary.generated_at)})
                </td>
                <td>
                  <Link to={`/summaries/${summary.id}`} className="button tertiary">
                    Open
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
};

export default SummariesPage;
