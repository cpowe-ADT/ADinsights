import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import DashboardState from '../components/DashboardState';
import { listAlerts, type AlertRule } from '../lib/phase2Api';
import { formatAbsoluteTime, formatRelativeTime } from '../lib/format';
import '../styles/phase2.css';
import '../styles/dashboard.css';

const AlertsPage = () => {
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [alerts, setAlerts] = useState<AlertRule[]>([]);
  const [error, setError] = useState('Unable to load alerts.');

  const load = useCallback(async () => {
    setState('loading');
    try {
      const data = await listAlerts();
      setAlerts(data);
      setState('ready');
    } catch (err) {
      setState('error');
      setError(err instanceof Error ? err.message : 'Unable to load alerts.');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (state === 'loading') {
    return <DashboardState variant="loading" layout="page" message="Loading alerts…" />;
  }

  if (state === 'error') {
    return (
      <DashboardState
        variant="error"
        layout="page"
        title="Alerts unavailable"
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
          <h1 className="dashboardHeading">Alert Rules</h1>
          <p className="phase2-page__subhead">Monitor thresholds, severities, and lookback windows.</p>
        </div>
        <button type="button" className="button secondary" onClick={() => void load()}>
          Refresh
        </button>
      </header>

      {alerts.length === 0 ? (
        <DashboardState
          variant="empty"
          layout="page"
          title="No alert rules"
          message="Create alert rules in admin to drive this view."
        />
      ) : (
        <table className="phase2-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Metric</th>
              <th>Rule</th>
              <th>Severity</th>
              <th>Updated</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {alerts.map((alert) => (
              <tr key={alert.id}>
                <td>{alert.name}</td>
                <td>{alert.metric}</td>
                <td>
                  {alert.comparison_operator} {alert.threshold} ({alert.lookback_hours}h)
                </td>
                <td>
                  <span className={`phase2-pill phase2-pill--${alert.severity}`}>{alert.severity}</span>
                </td>
                <td>
                  {formatRelativeTime(alert.updated_at)} ({formatAbsoluteTime(alert.updated_at)})
                </td>
                <td>
                  <Link to={`/alerts/${alert.id}`} className="button tertiary">
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

export default AlertsPage;
