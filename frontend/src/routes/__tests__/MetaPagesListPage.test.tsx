import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const airbyteMocks = vi.hoisted(() => ({
  loadSocialConnectionStatus: vi.fn(),
}));

import MetaPagesListPage from '../MetaPagesListPage';

const storeMock = vi.hoisted(() => ({
  state: {
    pagesStatus: 'loaded' as const,
    pages: [] as Array<{
      id: string;
      page_id: string;
      name: string;
      category?: string | null;
      can_analyze: boolean;
      is_default: boolean;
      last_synced_at?: string | null;
    }>,
    missingRequiredPermissions: [] as string[],
    error: undefined as string | undefined,
    loadPages: vi.fn().mockResolvedValue(undefined),
    connectOAuthStart: vi.fn().mockResolvedValue(undefined),
    selectDefaultPage: vi.fn().mockResolvedValue(undefined),
  },
}));

vi.mock('../../state/useMetaPageInsightsStore', () => ({
  default: (selector: (state: typeof storeMock.state) => unknown) => selector(storeMock.state),
}));

vi.mock('../../lib/airbyte', () => ({
  loadSocialConnectionStatus: airbyteMocks.loadSocialConnectionStatus,
}));

describe('MetaPagesListPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    storeMock.state.pagesStatus = 'loaded';
    storeMock.state.pages = [];
    storeMock.state.missingRequiredPermissions = [];
    storeMock.state.error = undefined;
    airbyteMocks.loadSocialConnectionStatus.mockResolvedValue({
      generated_at: '2026-04-04T15:00:00Z',
      platforms: [],
    });
  });

  it('shows connect socials and home recovery paths when no pages are loaded', async () => {
    render(
      <MemoryRouter>
        <MetaPagesListPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText('No Pages available')).toBeInTheDocument();
    expect(
      screen.getByText(/This screen lists Facebook Pages only\./i),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Connect socials' })).toHaveAttribute(
      'href',
      '/dashboards/data-sources?sources=social',
    );
    expect(screen.getByRole('link', { name: 'Meta accounts' })).toHaveAttribute(
      'href',
      '/dashboards/meta/accounts',
    );
    expect(screen.getByRole('link', { name: 'Connection status' })).toHaveAttribute(
      'href',
      '/dashboards/meta/status',
    );
    expect(screen.getByRole('button', { name: 'Connect socials' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Home' })).toBeInTheDocument();
    expect(storeMock.state.loadPages).toHaveBeenCalledTimes(1);
  });

  it('shows reconnect guidance when required page insights permissions are missing', async () => {
    storeMock.state.pages = [
      {
        id: '1',
        page_id: 'page-1',
        name: 'Page 1',
        can_analyze: true,
        is_default: true,
      },
    ];
    storeMock.state.missingRequiredPermissions = ['pages_read_engagement'];

    render(
      <MemoryRouter>
        <MetaPagesListPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText('Reconnect Meta to restore Page Insights')).toBeInTheDocument();
    expect(screen.getByText(/pages_read_engagement/)).toBeInTheDocument();
  });

  it('uses rerequest oauth when reconnecting after a permissions gap', async () => {
    const user = userEvent.setup();
    storeMock.state.pages = [
      {
        id: '1',
        page_id: 'page-1',
        name: 'Page 1',
        can_analyze: true,
        is_default: true,
      },
    ];
    storeMock.state.missingRequiredPermissions = ['pages_read_engagement'];

    render(
      <MemoryRouter>
        <MetaPagesListPage />
      </MemoryRouter>,
    );

    await user.click(await screen.findByRole('button', { name: 'Reconnect Meta' }));
    expect(storeMock.state.connectOAuthStart).toHaveBeenCalledWith({ authType: 'rerequest' });
  });

  it('shows restore CTA when marketing access is orphaned', async () => {
    airbyteMocks.loadSocialConnectionStatus.mockResolvedValue({
      generated_at: '2026-04-04T15:00:00Z',
      platforms: [
        {
          platform: 'meta',
          display_name: 'Meta (Facebook)',
          status: 'started_not_complete',
          reason: {
            code: 'orphaned_marketing_access',
            message: 'Meta Page Insights is connected, but marketing access must be restored.',
          },
          last_checked_at: '2026-04-04T15:00:00Z',
          last_synced_at: null,
          actions: ['recover_marketing_access', 'view'],
          metadata: {
            has_recoverable_marketing_access: true,
          },
        },
      ],
    });

    render(
      <MemoryRouter>
        <MetaPagesListPage />
      </MemoryRouter>,
    );

    expect((await screen.findAllByText('Restore Meta marketing access')).length).toBeGreaterThan(0);
  });
});
