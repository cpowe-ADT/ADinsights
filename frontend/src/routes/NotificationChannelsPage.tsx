import { useCallback, useEffect, useState, type FormEvent } from 'react';

import DashboardState from '../components/DashboardState';
import {
  listNotificationChannels,
  createNotificationChannel,
  deleteNotificationChannel,
  type NotificationChannel,
} from '../lib/phase2Api';
import '../styles/phase2.css';
import '../styles/dashboard.css';

const CHANNEL_TYPES: { value: NotificationChannel['channel_type']; label: string }[] = [
  { value: 'email', label: 'Email' },
  { value: 'webhook', label: 'Webhook' },
  { value: 'slack', label: 'Slack' },
];

const NotificationChannelsPage = () => {
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [channels, setChannels] = useState<NotificationChannel[]>([]);
  const [error, setError] = useState('Unable to load notification channels.');

  const [name, setName] = useState('');
  const [channelType, setChannelType] = useState<NotificationChannel['channel_type']>('email');
  const [configValue, setConfigValue] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    setState('loading');
    try {
      const data = await listNotificationChannels();
      setChannels(data);
      setState('ready');
    } catch (err) {
      setState('error');
      setError(err instanceof Error ? err.message : 'Unable to load notification channels.');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !configValue.trim()) return;
    setSubmitting(true);
    try {
      const configKey = channelType === 'email' ? 'emails' : 'url';
      await createNotificationChannel({
        name: name.trim(),
        channel_type: channelType,
        config: { [configKey]: configValue.trim() },
      });
      setName('');
      setConfigValue('');
      await load();
    } catch {
      // Keep form state on error so user can retry
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (channelId: string) => {
    try {
      await deleteNotificationChannel(channelId);
      setChannels((prev) => prev.filter((ch) => ch.id !== channelId));
    } catch {
      // Silently ignore; user can retry
    }
  };

  if (state === 'loading') {
    return <DashboardState variant="loading" layout="page" message="Loading notification channels..." />;
  }

  if (state === 'error') {
    return (
      <DashboardState
        variant="error"
        layout="page"
        title="Notification channels unavailable"
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
          <p className="dashboardEyebrow">Settings</p>
          <h1 className="dashboardHeading">Notification Channels</h1>
          <p className="phase2-page__subhead">
            Configure where alert notifications are delivered.
          </p>
        </div>
      </header>

      <article className="phase2-card">
        <h3>Create channel</h3>
        <form onSubmit={(e) => void handleCreate(e)} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxWidth: 480 }}>
          <label>
            Name
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Team Slack"
              required
              className="phase2-input"
            />
          </label>
          <label>
            Type
            <select
              value={channelType}
              onChange={(e) => setChannelType(e.target.value as NotificationChannel['channel_type'])}
              className="phase2-input"
            >
              {CHANNEL_TYPES.map((ct) => (
                <option key={ct.value} value={ct.value}>
                  {ct.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            {channelType === 'email' ? 'Emails (comma-separated)' : 'URL'}
            <input
              type="text"
              value={configValue}
              onChange={(e) => setConfigValue(e.target.value)}
              placeholder={channelType === 'email' ? 'a@example.com, b@example.com' : 'https://hooks.example.com/...'}
              required
              className="phase2-input"
            />
          </label>
          <button type="submit" className="button primary" disabled={submitting}>
            {submitting ? 'Creating...' : 'Create channel'}
          </button>
        </form>
      </article>

      {channels.length === 0 ? (
        <DashboardState
          variant="empty"
          layout="page"
          title="No notification channels"
          message="Create a channel above to start receiving alert notifications."
        />
      ) : (
        <table className="phase2-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Active</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {channels.map((ch) => (
              <tr key={ch.id}>
                <td>{ch.name}</td>
                <td>{ch.channel_type}</td>
                <td>{ch.is_active ? 'Yes' : 'No'}</td>
                <td>
                  <button
                    type="button"
                    className="button tertiary"
                    onClick={() => void handleDelete(ch.id)}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
};

export default NotificationChannelsPage;
