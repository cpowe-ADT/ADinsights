import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import NotificationChannelsPage from '../NotificationChannelsPage';

const phase2ApiMock = vi.hoisted(() => ({
  listNotificationChannels: vi.fn(),
  deleteNotificationChannel: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => phase2ApiMock);

describe('NotificationChannelsPage', () => {
  beforeEach(() => {
    phase2ApiMock.listNotificationChannels.mockResolvedValue([]);
    phase2ApiMock.deleteNotificationChannel.mockResolvedValue(undefined);
    vi.restoreAllMocks();
  });

  it('renders channel list with name and type', async () => {
    phase2ApiMock.listNotificationChannels.mockResolvedValue([
      {
        id: 'ch-1',
        name: 'Slack #alerts',
        channel_type: 'slack',
        config: {},
        is_active: true,
        created_at: '2026-04-01T00:00:00Z',
        updated_at: '2026-04-01T00:00:00Z',
      },
      {
        id: 'ch-2',
        name: 'Team Email',
        channel_type: 'email',
        config: {},
        is_active: false,
        created_at: '2026-04-01T00:00:00Z',
        updated_at: '2026-04-01T00:00:00Z',
      },
    ]);

    render(
      <MemoryRouter>
        <NotificationChannelsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText('Slack #alerts')).toBeInTheDocument());
    expect(screen.getByText('Team Email')).toBeInTheDocument();
    expect(screen.getByText('slack')).toBeInTheDocument();
    expect(screen.getByText('email')).toBeInTheDocument();
  });

  it('shows the create form', async () => {
    phase2ApiMock.listNotificationChannels.mockResolvedValue([]);

    render(
      <MemoryRouter>
        <NotificationChannelsPage />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: /create channel/i })).toBeInTheDocument(),
    );
    expect(screen.getByRole('button', { name: /create channel/i })).toBeInTheDocument();
  });

  it('shows error state when API fails', async () => {
    phase2ApiMock.listNotificationChannels.mockRejectedValue(new Error('Network failure'));

    render(
      <MemoryRouter>
        <NotificationChannelsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('Notification channels unavailable')).toBeInTheDocument();
    });
    expect(screen.getByText('Network failure')).toBeInTheDocument();
  });

  it('renders the empty state when no channels exist', async () => {
    phase2ApiMock.listNotificationChannels.mockResolvedValue([]);

    render(
      <MemoryRouter>
        <NotificationChannelsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText('No notification channels')).toBeInTheDocument());
  });

  it('calls window.confirm before deleting a channel', async () => {
    const user = userEvent.setup();
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);

    phase2ApiMock.listNotificationChannels.mockResolvedValue([
      {
        id: 'ch-1',
        name: 'Slack #alerts',
        channel_type: 'slack',
        config: {},
        is_active: true,
        created_at: '2026-04-01T00:00:00Z',
        updated_at: '2026-04-01T00:00:00Z',
      },
    ]);

    render(
      <MemoryRouter>
        <NotificationChannelsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText('Slack #alerts')).toBeInTheDocument());

    await user.click(screen.getByRole('button', { name: /delete/i }));

    expect(confirmSpy).toHaveBeenCalledWith('Delete this notification channel?');
    expect(phase2ApiMock.deleteNotificationChannel).not.toHaveBeenCalled();
  });

  it('proceeds with deletion when confirm is accepted', async () => {
    const user = userEvent.setup();
    vi.spyOn(window, 'confirm').mockReturnValue(true);

    phase2ApiMock.listNotificationChannels.mockResolvedValue([
      {
        id: 'ch-1',
        name: 'Slack #alerts',
        channel_type: 'slack',
        config: {},
        is_active: true,
        created_at: '2026-04-01T00:00:00Z',
        updated_at: '2026-04-01T00:00:00Z',
      },
    ]);

    render(
      <MemoryRouter>
        <NotificationChannelsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText('Slack #alerts')).toBeInTheDocument());

    await user.click(screen.getByRole('button', { name: /delete/i }));

    await waitFor(() =>
      expect(phase2ApiMock.deleteNotificationChannel).toHaveBeenCalledWith('ch-1'),
    );
  });
});
