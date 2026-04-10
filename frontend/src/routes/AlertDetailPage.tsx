import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import DashboardState from '../components/DashboardState';
import {
  deleteAlert,
  getAlert,
  updateAlert,
  listNotificationChannels,
  type AlertRule,
  type NotificationChannel,
} from '../lib/phase2Api';
import { formatAbsoluteTime, formatRelativeTime } from '../lib/format';
import '../styles/phase2.css';
import '../styles/dashboard.css';

const AlertDetailPage = () => {
  const { alertId } = useParams<{ alertId: string }>();
  const navigate = useNavigate();
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [alert, setAlert] = useState<AlertRule | null>(null);
  const [error, setError] = useState('Unable to load alert.');
  const [channels, setChannels] = useState<NotificationChannel[]>([]);
  const [selectedChannelIds, setSelectedChannelIds] = useState<string[]>([]);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    if (!alertId) {
      setState('error');
      setError('Alert ID is missing.');
      return;
    }

    setState('loading');
    try {
      const [data, channelData] = await Promise.all([
        getAlert(alertId),
        listNotificationChannels(),
      ]);
      setAlert(data);
      setChannels(channelData);
      setSelectedChannelIds(data.notification_channels ?? []);
      setState('ready');
    } catch (err) {
      setState('error');
      setError(err instanceof Error ? err.message : 'Unable to load alert.');
    }
  }, [alertId]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleChannelToggle = async (channelId: string, checked: boolean) => {
    if (!alertId) return;
    const updated = checked
      ? [...selectedChannelIds, channelId]
      : selectedChannelIds.filter((id) => id !== channelId);
    setSelectedChannelIds(updated);
    try {
      await updateAlert(alertId, { notification_channels: updated });
    } catch {
      // Revert on failure
      setSelectedChannelIds(selectedChannelIds);
    }
  };

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
          <button
            type="button"
            className="button tertiary"
            style={{ color: 'var(--color-danger, #dc2626)' }}
            disabled={deleting}
            onClick={() => {
              if (!alertId) return;
              if (!window.confirm('Delete this alert rule?')) return;
              setDeleting(true);
              deleteAlert(alertId)
                .then(() => navigate('/alerts'))
                .catch((err) => {
                  setDeleting(false);
                  setError(err instanceof Error ? err.message : 'Unable to delete alert.');
                  setState('error');
                });
            }}
          >
            {deleting ? 'Deleting...' : 'Delete'}
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

      <article className="phase2-card">
        <h3>Notification Channels</h3>
        {channels.length === 0 ? (
          <p>No notification channels configured. <Link to="/settings/notifications">Create one</Link>.</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {channels.map((ch) => (
              <label key={ch.id} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <input
                  type="checkbox"
                  checked={selectedChannelIds.includes(ch.id)}
                  onChange={(e) => void handleChannelToggle(ch.id, e.target.checked)}
                />
                {ch.name} ({ch.channel_type})
              </label>
            ))}
          </div>
        )}
      </article>
    </section>
  );
};

export default AlertDetailPage;
