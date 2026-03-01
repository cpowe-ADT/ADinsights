import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import DashboardState from '../components/DashboardState';
import { getAlert, type AlertRule } from '../lib/phase2Api';
import { formatAbsoluteTime, formatRelativeTime } from '../lib/format';
import '../styles/phase2.css';
import '../styles/dashboard.css';

const AlertDetailPage = () => {
  const { alertId } = useParams<{ alertId: string }>();
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [alert, setAlert] = useState<AlertRule | null>(null);
  const [error, setError] = useState('Unable to load alert.');

  const load = useCallback(async () => {
    if (!alertId) {
      setState('error');
      setError('Alert ID is missing.');
      return;
    }

    setState('loading');
    try {
      const data = await getAlert(alertId);
      setAlert(data);
      setState('ready');
    } catch (err) {
      setState('error');
      setError(err instanceof Error ? err.message : 'Unable to load alert.');
    }
  }, [alertId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (state === 'loading') {
    return <DashboardState variant="loading" layout="page" message="Loading alert detail…" />;
  }

  if (state === 'error' || !alert) {
    return (
      <DashboardState
        variant="error"
        layout="page"
        title="Alert unavailable"
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
          <h1 className="dashboardHeading">{alert.name}</h1>
          <p className="phase2-page__subhead">Detailed threshold and lifecycle metadata.</p>
        </div>
        <div className="phase2-row-actions">
          <Link to="/alerts" className="button tertiary">
            Back to alerts
          </Link>
          <button type="button" className="button secondary" onClick={() => void load()}>
            Refresh
          </button>
        </div>
      </header>

      <article className="phase2-card">
        <h3>Rule details</h3>
        <p>
          Metric: <strong>{alert.metric}</strong>
        </p>
        <p>
          Condition: <strong>{alert.comparison_operator}</strong> <strong>{alert.threshold}</strong>
        </p>
        <p>
          Lookback: <strong>{alert.lookback_hours} hours</strong>
        </p>
        <p>
          Severity:{' '}
          <span className={`phase2-pill phase2-pill--${alert.severity}`}>{alert.severity}</span>
        </p>
        <p>
          Updated {formatRelativeTime(alert.updated_at)} ({formatAbsoluteTime(alert.updated_at)})
        </p>
      </article>
    </section>
  );
};

export default AlertDetailPage;
