import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import DashboardState from '../components/DashboardState';
import SkeletonLoader from '../components/SkeletonLoader';
import {
  deleteAlert,
  getAlert,
  pauseAlert,
  resumeAlert,
  updateAlert,
  listNotificationChannels,
  type AlertRule,
  type NotificationChannel,
} from '../lib/phase2Api';
import { formatAbsoluteTime, formatRelativeTime } from '../lib/format';
import { useToastStore } from '../stores/useToastStore';
import '../styles/phase2.css';
import '../styles/dashboard.css';
import '../styles/skeleton.css';

type PauseDurationKey = '1h' | '4h' | '24h' | '7d' | 'indefinite';

const PAUSE_DURATION_OPTIONS: { value: PauseDurationKey; label: string; hours?: number }[] = [
  { value: '1h', label: '1 hour', hours: 1 },
  { value: '4h', label: '4 hours', hours: 4 },
  { value: '24h', label: '24 hours', hours: 24 },
  { value: '7d', label: '7 days', hours: 168 },
  { value: 'indefinite', label: 'Indefinite' },
];

type EditFormState = {
  name: string;
  metric: string;
  comparison_operator: string;
  threshold: string;
  lookback_hours: string;
  severity: string;
};

const buildEditState = (alert: AlertRule): EditFormState => ({
  name: alert.name,
  metric: alert.metric,
  comparison_operator: alert.comparison_operator,
  threshold: alert.threshold,
  lookback_hours: String(alert.lookback_hours),
  severity: alert.severity,
});

const AlertDetailPage = () => {
  const { alertId } = useParams<{ alertId: string }>();
  const navigate = useNavigate();
  const addToast = useToastStore((s) => s.addToast);
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [alert, setAlert] = useState<AlertRule | null>(null);
  const [error, setError] = useState('Unable to load alert.');
  const [channels, setChannels] = useState<NotificationChannel[]>([]);
  const [selectedChannelIds, setSelectedChannelIds] = useState<string[]>([]);
  const [deleting, setDeleting] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [pauseDuration, setPauseDuration] = useState<PauseDurationKey>('indefinite');
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState<EditFormState | null>(null);
  const [savingEdit, setSavingEdit] = useState(false);

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
      addToast('Notification channels updated');
    } catch {
      setSelectedChannelIds(selectedChannelIds);
      addToast('Failed to update channels', 'error');
    }
  };

  const handleToggle = useCallback(async () => {
    if (!alertId || !alert) return;
    setToggling(true);
    try {
      let updated: AlertRule;
      if (alert.is_active) {
        const selected = PAUSE_DURATION_OPTIONS.find((opt) => opt.value === pauseDuration);
        const body =
          selected && typeof selected.hours === 'number'
            ? { duration_hours: selected.hours }
            : {};
        updated = await pauseAlert(alertId, body);
        const pausedUntil = updated.paused_until;
        addToast(
          `Alert paused${pausedUntil ? ` until ${formatAbsoluteTime(pausedUntil)}` : ''}`,
        );
      } else {
        updated = await resumeAlert(alertId);
        addToast('Alert resumed');
      }
      setAlert(updated);
    } catch {
      addToast('Failed to update alert', 'error');
    } finally {
      setToggling(false);
    }
  }, [alertId, alert, addToast, pauseDuration]);

  const beginEdit = useCallback(() => {
    if (!alert) return;
    setEditForm(buildEditState(alert));
    setEditing(true);
  }, [alert]);

  const cancelEdit = useCallback(() => {
    setEditing(false);
    setEditForm(null);
  }, []);

  const saveEdit = useCallback(async () => {
    if (!alertId || !editForm) return;
    setSavingEdit(true);
    try {
      const updated = await updateAlert(alertId, {
        name: editForm.name,
        metric: editForm.metric,
        comparison_operator: editForm.comparison_operator,
        threshold: editForm.threshold,
        lookback_hours: Number(editForm.lookback_hours),
        severity: editForm.severity,
      });
      setAlert(updated);
      setEditing(false);
      setEditForm(null);
      addToast('Alert rule updated');
    } catch {
      addToast('Failed to update alert', 'error');
    } finally {
      setSavingEdit(false);
    }
  }, [alertId, editForm, addToast]);

  if (state === 'loading') {
    return (
      <section className="phase2-page">
        <header className="phase2-page__header">
          <div>
            <p className="dashboardEyebrow">Alerts</p>
            <h1 className="dashboardHeading">Alert Detail</h1>
          </div>
        </header>
        <SkeletonLoader variant="card" count={2} />
      </section>
    );
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
          {!editing ? (
            <button type="button" className="button secondary" onClick={beginEdit}>
              Edit
            </button>
          ) : null}
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
        {editing && editForm ? (
          <form
            className="phase2-form"
            onSubmit={(event) => {
              event.preventDefault();
              void saveEdit();
            }}
          >
            <label className="phase2-form__field" htmlFor="alert-edit-name">
              <span>Name</span>
              <input
                id="alert-edit-name"
                value={editForm.name}
                onChange={(event) =>
                  setEditForm((prev) => (prev ? { ...prev, name: event.target.value } : prev))
                }
                disabled={savingEdit}
              />
            </label>

            <label className="phase2-form__field" htmlFor="alert-edit-metric">
              <span>Metric</span>
              <input
                id="alert-edit-metric"
                value={editForm.metric}
                onChange={(event) =>
                  setEditForm((prev) => (prev ? { ...prev, metric: event.target.value } : prev))
                }
                disabled={savingEdit}
              />
            </label>

            <label className="phase2-form__field" htmlFor="alert-edit-operator">
              <span>Operator</span>
              <select
                id="alert-edit-operator"
                value={editForm.comparison_operator}
                onChange={(event) =>
                  setEditForm((prev) =>
                    prev ? { ...prev, comparison_operator: event.target.value } : prev,
                  )
                }
                disabled={savingEdit}
              >
                <option value="gt">Greater than</option>
                <option value="gte">Greater than or equal</option>
                <option value="lt">Less than</option>
                <option value="lte">Less than or equal</option>
                <option value="eq">Equal to</option>
              </select>
            </label>

            <label className="phase2-form__field" htmlFor="alert-edit-threshold">
              <span>Threshold</span>
              <input
                id="alert-edit-threshold"
                type="number"
                step="any"
                value={editForm.threshold}
                onChange={(event) =>
                  setEditForm((prev) =>
                    prev ? { ...prev, threshold: event.target.value } : prev,
                  )
                }
                disabled={savingEdit}
              />
            </label>

            <label className="phase2-form__field" htmlFor="alert-edit-lookback">
              <span>Lookback (hours)</span>
              <input
                id="alert-edit-lookback"
                type="number"
                min="1"
                value={editForm.lookback_hours}
                onChange={(event) =>
                  setEditForm((prev) =>
                    prev ? { ...prev, lookback_hours: event.target.value } : prev,
                  )
                }
                disabled={savingEdit}
              />
            </label>

            <label className="phase2-form__field" htmlFor="alert-edit-severity">
              <span>Severity</span>
              <select
                id="alert-edit-severity"
                value={editForm.severity}
                onChange={(event) =>
                  setEditForm((prev) => (prev ? { ...prev, severity: event.target.value } : prev))
                }
                disabled={savingEdit}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </label>

            <div className="phase2-row-actions">
              <button
                type="button"
                className="button tertiary"
                onClick={cancelEdit}
                disabled={savingEdit}
              >
                Cancel
              </button>
              <button type="submit" className="button primary" disabled={savingEdit}>
                {savingEdit ? 'Saving…' : 'Save'}
              </button>
            </div>
          </form>
        ) : (
          <>
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
              Status:{' '}
              <span className={`phase2-pill phase2-pill--${alert.is_active ? 'fresh' : 'stale'}`}>
                {alert.is_active ? 'Active' : 'Paused'}
              </span>
              {alert.is_active ? (
                <select
                  aria-label="Pause duration"
                  value={pauseDuration}
                  onChange={(event) => setPauseDuration(event.target.value as PauseDurationKey)}
                  disabled={toggling}
                  style={{ marginLeft: '0.5rem' }}
                >
                  {PAUSE_DURATION_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              ) : null}
              <button
                type="button"
                className="button tertiary"
                style={{ marginLeft: '0.5rem' }}
                disabled={toggling}
                onClick={() => void handleToggle()}
              >
                {alert.is_active ? 'Pause' : 'Resume'}
              </button>
            </p>
            {alert.paused_until ? (
              <p className="phase2-note">
                Auto-resumes {formatRelativeTime(alert.paused_until)} (
                {formatAbsoluteTime(alert.paused_until)})
              </p>
            ) : null}
            <p>
              Updated {formatRelativeTime(alert.updated_at)} ({formatAbsoluteTime(alert.updated_at)})
            </p>
          </>
        )}
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
