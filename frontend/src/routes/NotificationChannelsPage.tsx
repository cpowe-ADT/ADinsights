import { useCallback, useEffect, useState } from 'react';

import DashboardState from '../components/DashboardState';
import {
  deleteNotificationChannel,
  listNotificationChannels,
  type NotificationChannel,
} from '../lib/phase2Api';
import { formatAbsoluteTime, formatRelativeTime } from '../lib/format';
import '../styles/phase2.css';
import '../styles/dashboard.css';

const NotificationChannelsPage = () => {
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [channels, setChannels] = useState<NotificationChannel[]>([]);
  const [error, setError] = useState('Unable to load notification channels.');
  const [deletingId, setDeletingId] = useState<string | null>(null);

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

  const handleDelete = useCallback(
    async (channelId: string) => {
      if (!window.confirm('Delete this notification channel?')) {
        return;
      }
      setDeletingId(channelId);
      try {
        await deleteNotificationChannel(channelId);
        await load();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to delete channel.');
      } finally {
        setDeletingId(null);
      }
    },
    [load],
  );

  if (state === 'loading') {
    return (
      <DashboardState variant="loading" layout="page" message="Loading notification channels…" />
    );
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
            Manage delivery channels for alert notifications.
          </p>
        </div>
        <button type="button" className="button secondary" onClick={() => void load()}>
          Refresh
        </button>
      </header>

      {channels.length === 0 ? (
        <DashboardState
          variant="empty"
          layout="page"
          title="No notification channels"
          message="Add a notification channel to start receiving alert deliveries."
        />
      ) : (
        <table className="phase2-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Status</th>
              <th>Updated</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {channels.map((channel) => (
              <tr key={channel.id}>
                <td>{channel.name}</td>
                <td>{channel.channel_type}</td>
                <td>
                  <span
                    className={`phase2-pill phase2-pill--${channel.is_active ? 'fresh' : 'inactive'}`}
                  >
                    {channel.is_active ? 'active' : 'inactive'}
                  </span>
                </td>
                <td>
                  {formatRelativeTime(channel.updated_at)} (
                  {formatAbsoluteTime(channel.updated_at)})
                </td>
                <td>
                  <button
                    type="button"
                    className="button tertiary"
                    disabled={deletingId !== null}
                    onClick={() => void handleDelete(channel.id)}
                  >
                    {deletingId === channel.id ? 'Deleting…' : 'Delete'}
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
