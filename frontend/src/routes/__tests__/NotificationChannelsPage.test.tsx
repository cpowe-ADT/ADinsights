import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import NotificationChannelsPage from '../NotificationChannelsPage';

const phase2ApiMock = vi.hoisted(() => ({
  listNotificationChannels: vi.fn(),
  createNotificationChannel: vi.fn(),
  deleteNotificationChannel: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  listNotificationChannels: phase2ApiMock.listNotificationChannels,
  createNotificationChannel: phase2ApiMock.createNotificationChannel,
  deleteNotificationChannel: phase2ApiMock.deleteNotificationChannel,
}));

const sampleChannel = {
  id: 'ch-1',
  name: 'Team Slack',
  channel_type: 'slack' as const,
  config: { url: 'https://hooks.slack.com/xxx' },
  is_active: true,
  created_at: '2026-04-01T00:00:00Z',
  updated_at: '2026-04-01T00:00:00Z',
};

describe('NotificationChannelsPage', () => {
  beforeEach(() => {
    phase2ApiMock.listNotificationChannels.mockResolvedValue([]);
    phase2ApiMock.createNotificationChannel.mockResolvedValue(sampleChannel);
    phase2ApiMock.deleteNotificationChannel.mockResolvedValue(undefined);
  });

  it('renders empty state when no channels exist', async () => {
    render(
      <MemoryRouter>
        <NotificationChannelsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.listNotificationChannels).toHaveBeenCalled());
    expect(screen.getByText(/no notification channels/i)).toBeInTheDocument();
  });

  it('renders channel list', async () => {
    phase2ApiMock.listNotificationChannels.mockResolvedValue([sampleChannel]);

    render(
      <MemoryRouter>
        <NotificationChannelsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText('Team Slack')).toBeInTheDocument());
    expect(screen.getByText('slack')).toBeInTheDocument();
  });

  it('create form submits a new channel', async () => {
    phase2ApiMock.listNotificationChannels
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([sampleChannel]);

    render(
      <MemoryRouter>
        <NotificationChannelsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.listNotificationChannels).toHaveBeenCalled());

    fireEvent.change(screen.getByPlaceholderText(/e\.g\. Team Slack/i), {
      target: { value: 'Team Slack' },
    });
    fireEvent.change(screen.getByPlaceholderText(/a@example\.com/i), {
      target: { value: 'dev@example.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: /create channel/i }));

    await waitFor(() =>
      expect(phase2ApiMock.createNotificationChannel).toHaveBeenCalledWith({
        name: 'Team Slack',
        channel_type: 'email',
        config: { emails: 'dev@example.com' },
      }),
    );
  });

  it('delete button removes a channel', async () => {
    phase2ApiMock.listNotificationChannels.mockResolvedValue([sampleChannel]);

    render(
      <MemoryRouter>
        <NotificationChannelsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText('Team Slack')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /delete/i }));

    await waitFor(() =>
      expect(phase2ApiMock.deleteNotificationChannel).toHaveBeenCalledWith('ch-1'),
    );
  });

  it('shows loading state', () => {
    phase2ApiMock.listNotificationChannels.mockReturnValue(new Promise(() => {}));

    render(
      <MemoryRouter>
        <NotificationChannelsPage />
      </MemoryRouter>,
    );

    expect(screen.getByText(/loading notification channels/i)).toBeInTheDocument();
  });

  it('shows error state', async () => {
    phase2ApiMock.listNotificationChannels.mockRejectedValue(new Error('Network error'));

    render(
      <MemoryRouter>
        <NotificationChannelsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText(/network error/i)).toBeInTheDocument());
  });
});
