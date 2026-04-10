import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import DashboardState from '../components/DashboardState';
import SkeletonLoader from '../components/SkeletonLoader';
import { getSummary, type AISummary } from '../lib/phase2Api';
import { formatAbsoluteTime, formatRelativeTime } from '../lib/format';
import '../styles/phase2.css';
import '../styles/dashboard.css';
import '../styles/skeleton.css';

const SummaryDetailPage = () => {
  const { summaryId } = useParams<{ summaryId: string }>();
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [summary, setSummary] = useState<AISummary | null>(null);
  const [error, setError] = useState('Unable to load summary.');
  const [payloadExpanded, setPayloadExpanded] = useState(false);

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
    return (
      <section className="phase2-page">
        <header className="phase2-page__header">
          <div>
            <p className="dashboardEyebrow">AI Summaries</p>
            <h1 className="dashboardHeading">Summary Detail</h1>
          </div>
        </header>
        <SkeletonLoader variant="card" count={2} />
      </section>
    );
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
            {' · '}Source: {summary.source}
            {summary.model_name && ` · Model: ${summary.model_name}`}
          </p>
        </div>
        <div className="phase2-row-actions">
          <span className={`phase2-pill phase2-pill--${summary.status}`}>{summary.status}</span>
          <span className={`phase2-pill phase2-pill--${summary.source === 'daily_summary' ? 'generated' : 'info'}`}>
            {summary.source === 'daily_summary' ? 'Daily summary' : 'Manual refresh'}
          </span>
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
        <h3>
          <button
            type="button"
            onClick={() => setPayloadExpanded(!payloadExpanded)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', font: 'inherit', fontWeight: 'inherit', padding: 0 }}
          >
            {payloadExpanded ? '▾' : '▸'} Raw payload
          </button>
        </h3>
        {payloadExpanded && (
          <pre className="phase2-json">{JSON.stringify(summary.payload, null, 2)}</pre>
        )}
      </article>
    </section>
  );
};

export default SummaryDetailPage;
