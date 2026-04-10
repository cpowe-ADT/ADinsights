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
