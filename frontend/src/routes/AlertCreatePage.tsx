import { type FormEvent, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import DashboardState from '../components/DashboardState';
import {
  createAlert,
  listNotificationChannels,
  type NotificationChannel,
} from '../lib/phase2Api';
import { canAccessCreatorUi } from '../lib/rbac';
import '../styles/phase2.css';
import '../styles/dashboard.css';

const AlertCreatePage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const canCreate = canAccessCreatorUi(user);

  const [name, setName] = useState('');
  const [metric, setMetric] = useState('');
  const [operator, setOperator] = useState('gt');
  const [threshold, setThreshold] = useState('');
  const [lookbackHours, setLookbackHours] = useState('24');
  const [severity, setSeverity] = useState('warning');
  const [channels, setChannels] = useState<NotificationChannel[]>([]);
  const [selectedChannelIds, setSelectedChannelIds] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listNotificationChannels()
      .then((data) => {
        if (!cancelled) {
          setChannels(data);
        }
      })
      .catch(() => {
        /* channels are optional — swallow errors */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const toggleChannel = (channelId: string) => {
    setSelectedChannelIds((prev) =>
      prev.includes(channelId) ? prev.filter((id) => id !== channelId) : [...prev, channelId],
    );
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!name.trim()) {
      setError('Alert name is required.');
      return;
    }
    if (!metric.trim()) {
      setError('Metric is required.');
      return;
    }
    if (!threshold.trim() || Number.isNaN(Number(threshold))) {
      setError('A valid numeric threshold is required.');
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const created = await createAlert({
        name: name.trim(),
        metric: metric.trim(),
        comparison_operator: operator,
        threshold: threshold.trim(),
        lookback_hours: Number(lookbackHours),
        severity,
        notification_channels: selectedChannelIds.length > 0 ? selectedChannelIds : undefined,
      });
      navigate(`/alerts/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create alert.');
    } finally {
      setSaving(false);
    }
  };

  if (!canCreate) {
    return (
      <DashboardState
        variant="empty"
        layout="page"
        title="Read-only alert access"
        message="Viewer access can review alerts, but cannot create new alert rules."
        actionLabel="Back to alerts"
        onAction={() => navigate('/alerts')}
      />
    );
  }

  return (
    <section className="phase2-page">
      <header>
        <p className="dashboardEyebrow">Alerts</p>
        <h1 className="dashboardHeading">Create Alert Rule</h1>
        <p className="phase2-page__subhead">
          Define a threshold rule to trigger alert notifications.
        </p>
      </header>

      <form className="phase2-form" onSubmit={submit}>
        <label className="phase2-form__field" htmlFor="alert-name">
          <span>Name</span>
          <input
            id="alert-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="High CPC alert"
            disabled={saving}
          />
        </label>

        <label className="phase2-form__field" htmlFor="alert-metric">
          <span>Metric</span>
          <input
            id="alert-metric"
            value={metric}
            onChange={(event) => setMetric(event.target.value)}
            placeholder="cpc"
            disabled={saving}
          />
        </label>

        <label className="phase2-form__field" htmlFor="alert-operator">
          <span>Operator</span>
          <select
            id="alert-operator"
            value={operator}
            onChange={(event) => setOperator(event.target.value)}
            disabled={saving}
          >
            <option value="gt">Greater than</option>
            <option value="gte">Greater than or equal</option>
            <option value="lt">Less than</option>
            <option value="lte">Less than or equal</option>
            <option value="eq">Equal to</option>
          </select>
        </label>

        <label className="phase2-form__field" htmlFor="alert-threshold">
          <span>Threshold</span>
          <input
            id="alert-threshold"
            type="number"
            step="any"
            value={threshold}
            onChange={(event) => setThreshold(event.target.value)}
            placeholder="5.00"
            disabled={saving}
          />
        </label>

        <label className="phase2-form__field" htmlFor="alert-lookback">
          <span>Lookback (hours)</span>
          <input
            id="alert-lookback"
            type="number"
            min="1"
            value={lookbackHours}
            onChange={(event) => setLookbackHours(event.target.value)}
            disabled={saving}
          />
        </label>

        <label className="phase2-form__field" htmlFor="alert-severity">
          <span>Severity</span>
          <select
            id="alert-severity"
            value={severity}
            onChange={(event) => setSeverity(event.target.value)}
            disabled={saving}
          >
            <option value="info">Info</option>
            <option value="warning">Warning</option>
            <option value="critical">Critical</option>
          </select>
        </label>

        <fieldset className="phase2-form__field">
          <legend>Notification Channels</legend>
          {channels.length === 0 ? (
            <p className="phase2-note">
              No notification channels configured.{' '}
              <Link to="/settings/notifications">Create one</Link> to receive alert notifications.
            </p>
          ) : (
            channels.map((channel) => (
              <label key={channel.id} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <input
                  type="checkbox"
                  checked={selectedChannelIds.includes(channel.id)}
                  onChange={() => toggleChannel(channel.id)}
                  disabled={saving}
                />
                <span>
                  {channel.name} ({channel.channel_type})
                </span>
              </label>
            ))
          )}
        </fieldset>

        {error ? <p className="status-message error">{error}</p> : null}

        <div className="phase2-row-actions">
          <button type="button" className="button tertiary" onClick={() => navigate('/alerts')}>
            Cancel
          </button>
          <button type="submit" className="button primary" disabled={saving}>
            {saving ? 'Creating...' : 'Create alert'}
          </button>
        </div>
      </form>
    </section>
  );
};

export default AlertCreatePage;
