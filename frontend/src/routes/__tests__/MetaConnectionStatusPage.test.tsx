import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import MetaConnectionStatusPage from '../MetaConnectionStatusPage';

const airbyteMocks = vi.hoisted(() => ({
  loadSocialConnectionStatus: vi.fn(),
  startMetaOAuth: vi.fn(),
}));

vi.mock('../../lib/airbyte', () => ({
  loadSocialConnectionStatus: airbyteMocks.loadSocialConnectionStatus,
}));

vi.mock('../../lib/metaPageInsights', () => ({
  startMetaOAuth: airbyteMocks.startMetaOAuth,
}));

describe('MetaConnectionStatusPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    airbyteMocks.startMetaOAuth.mockResolvedValue({
      authorize_url: 'https://facebook.com/dialog/oauth?rerequest=1',
      state: 'state',
      redirect_uri: 'http://localhost:5173/dashboards/data-sources',
    });
    airbyteMocks.loadSocialConnectionStatus.mockResolvedValue({
      generated_at: '2026-04-04T15:00:00Z',
      platforms: [],
    });
  });

  it('shows canonical setup and recovery actions when no status rows are available', async () => {
    render(
      <MemoryRouter>
        <MetaConnectionStatusPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText('No Meta status yet')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Connect socials' })).toHaveAttribute(
      'href',
      '/dashboards/data-sources?sources=social',
    );
    expect(screen.getByRole('link', { name: 'Facebook pages' })).toHaveAttribute(
      'href',
      '/dashboards/meta/pages',
    );
    expect(screen.getByRole('button', { name: 'Connect socials' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Facebook pages' })).toBeInTheDocument();
  });

  it('offers a rerequest reconnect path when page insights permissions are missing', async () => {
    const user = userEvent.setup();
    const originalLocation = window.location;
    const assignSpy = vi.fn();
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { assign: assignSpy },
    });
    airbyteMocks.loadSocialConnectionStatus.mockResolvedValue({
      generated_at: '2026-04-04T15:00:00Z',
      platforms: [
        {
          platform: 'meta',
          display_name: 'Meta (Facebook)',
          status: 'started_not_complete',
          reason: {
            code: 'page_insights_permissions_missing',
            message: 'Meta Page Insights is connected, but required permissions are missing: pages_show_list.',
          },
          last_checked_at: '2026-04-04T15:00:00Z',
          last_synced_at: null,
          actions: ['connect_oauth', 'view'],
          metadata: {},
        },
      ],
    });

    render(
      <MemoryRouter>
        <MetaConnectionStatusPage />
      </MemoryRouter>,
    );

    await user.click(await screen.findByRole('button', { name: 'Reconnect Meta' }));
    expect(airbyteMocks.startMetaOAuth).toHaveBeenCalledWith('rerequest');
    expect(assignSpy).toHaveBeenCalledWith('https://facebook.com/dialog/oauth?rerequest=1');

    Object.defineProperty(window, 'location', {
      configurable: true,
      value: originalLocation,
    });
  });

  it('surfaces restore CTA when marketing access is orphaned', async () => {
    airbyteMocks.loadSocialConnectionStatus.mockResolvedValue({
      generated_at: '2026-04-04T15:00:00Z',
      platforms: [
        {
          platform: 'meta',
          display_name: 'Meta (Facebook)',
          status: 'started_not_complete',
          reason: {
            code: 'orphaned_marketing_access',
            message:
              'Meta Page Insights is connected, but marketing account access has to be restored before ad account reporting can resume.',
          },
          last_checked_at: '2026-04-04T15:00:00Z',
          last_synced_at: null,
          actions: ['recover_marketing_access', 'view'],
          metadata: {
            has_recoverable_marketing_access: true,
            marketing_recovery_source: 'existing_meta_connection',
          },
        },
      ],
    });

    render(
      <MemoryRouter>
        <MetaConnectionStatusPage />
      </MemoryRouter>,
    );

    expect((await screen.findAllByText('Restore Meta marketing access')).length).toBeGreaterThan(0);
  });

  it('shows the reporting readiness stage when Meta status includes warehouse context', async () => {
    airbyteMocks.loadSocialConnectionStatus.mockResolvedValue({
      generated_at: '2026-04-04T15:00:00Z',
      platforms: [
        {
          platform: 'meta',
          display_name: 'Meta (Facebook)',
          status: 'active',
          reason: {
            code: 'active_direct_sync',
            message: 'Meta direct sync completed successfully with fresh reporting rows.',
          },
          last_checked_at: '2026-04-04T15:00:00Z',
          last_synced_at: '2026-04-04T14:55:00Z',
          actions: ['sync_now', 'view'],
          reporting_readiness: {
            stage: 'waiting_for_warehouse_snapshot',
            message: 'Meta connected. Direct sync complete. Waiting for the first warehouse snapshot.',
            auth_status: 'active',
            direct_sync_status: 'complete',
            warehouse_status: 'waiting_snapshot',
            dataset_live_reason: 'missing_snapshot',
            warehouse_adapter_enabled: true,
            snapshot_generated_at: null,
          },
          metadata: {},
        },
      ],
    });

    render(
      <MemoryRouter>
        <MetaConnectionStatusPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText('Reporting stage')).toBeInTheDocument();
    expect(screen.getByText('waiting_for_warehouse_snapshot')).toBeInTheDocument();
    expect(
      screen.getByText('Meta connected. Direct sync complete. Waiting for the first warehouse snapshot.'),
    ).toBeInTheDocument();
  });
});
