import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import DashboardState from '../components/DashboardState';
import { getSummary, type AISummary } from '../lib/phase2Api';
import { formatAbsoluteTime, formatRelativeTime } from '../lib/format';
import '../styles/phase2.css';
import '../styles/dashboard.css';

const SummaryDetailPage = () => {
  const { summaryId } = useParams<{ summaryId: string }>();
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [summary, setSummary] = useState<AISummary | null>(null);
  const [error, setError] = useState('Unable to load summary.');

  const load = useCallback(async () => {
    if (!summaryId) {
      setState('error');
      setError('Summary ID is missing.');
      return;
    }
    setState('loading');
    try {
      const data = await getSummary(summaryId);
      setSummary(data);
      setState('ready');
    } catch (err) {
      setState('error');
      setError(err instanceof Error ? err.message : 'Unable to load summary.');
    }
  }, [summaryId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (state === 'loading') {
    return <DashboardState variant="loading" layout="page" message="Loading summary detail…" />;
  }

  if (state === 'error' || !summary) {
    return (
      <DashboardState
        variant="error"
        layout="page"
        title="Summary unavailable"
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
          <h1 className="dashboardHeading">{summary.title}</h1>
          <p className="phase2-page__subhead">
            Generated {formatRelativeTime(summary.generated_at)} ({formatAbsoluteTime(summary.generated_at)})
          </p>
        </div>
        <div className="phase2-row-actions">
          <span className={`phase2-pill phase2-pill--${summary.status}`}>{summary.status}</span>
          <Link to="/summaries" className="button tertiary">
            Back to summaries
          </Link>
        </div>
      </header>

      <article className="phase2-card">
        <h3>Summary text</h3>
        <p>{summary.summary}</p>
      </article>

      <article className="phase2-card">
        <h3>Payload snapshot</h3>
        <pre className="phase2-json">{JSON.stringify(summary.payload, null, 2)}</pre>
      </article>
    </section>
  );
};

export default SummaryDetailPage;
