import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import ReportsTabSection from '../tab-sections/ReportsTabSection';
import type { GoogleAdsSavedView } from '../../../../lib/googleAdsDashboard';

const googleAdsDashboardMock = vi.hoisted(() => ({
  createGoogleAdsExport: vi.fn(),
  fetchGoogleAdsExportStatus: vi.fn(),
  fetchGoogleAdsSavedViews: vi.fn(),
  createGoogleAdsSavedView: vi.fn(),
  verifyGoogleAdsSavedView: vi.fn(),
}));

vi.mock('../../../../lib/googleAdsDashboard', async () => {
  const actual = await vi.importActual<typeof import('../../../../lib/googleAdsDashboard')>(
    '../../../../lib/googleAdsDashboard',
  );
  return {
    ...actual,
    createGoogleAdsExport: googleAdsDashboardMock.createGoogleAdsExport,
    fetchGoogleAdsExportStatus: googleAdsDashboardMock.fetchGoogleAdsExportStatus,
    fetchGoogleAdsSavedViews: googleAdsDashboardMock.fetchGoogleAdsSavedViews,
    createGoogleAdsSavedView: googleAdsDashboardMock.createGoogleAdsSavedView,
    verifyGoogleAdsSavedView: googleAdsDashboardMock.verifyGoogleAdsSavedView,
  };
});

const savedView = (id: string, name: string): GoogleAdsSavedView => ({
  id,
  name,
  description: '',
  filters: {},
  columns: [],
  is_shared: false,
  created_at: '2026-04-01T00:00:00Z',
  updated_at: '2026-04-01T00:00:00Z',
});

const cleanVerify = (id: string, name: string) => ({
  id,
  name,
  drift: false,
  unknown_filter_keys: [],
  unknown_columns: [],
  checked_against_version: 'google-ads-v23',
});

const driftVerify = (id: string, name: string) => ({
  id,
  name,
  drift: true,
  unknown_filter_keys: ['banana'],
  unknown_columns: [],
  checked_against_version: 'google-ads-v23',
});

describe('ReportsTabSection — GA-B2 drift banner', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    googleAdsDashboardMock.fetchGoogleAdsSavedViews.mockResolvedValue([]);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('no banner when all saved views verify clean', async () => {
    const views = [savedView('v1', 'Alpha'), savedView('v2', 'Beta'), savedView('v3', 'Gamma')];
    googleAdsDashboardMock.verifyGoogleAdsSavedView.mockImplementation((id: string) =>
      Promise.resolve(cleanVerify(id, id.toUpperCase())),
    );

    render(<ReportsTabSection initialSavedViews={views} />);

    // Wait long enough for the verify promises to settle.
    await waitFor(() => {
      expect(googleAdsDashboardMock.verifyGoogleAdsSavedView).toHaveBeenCalledTimes(3);
    });
    // Flush microtasks from Promise.allSettled.
    await Promise.resolve();
    await Promise.resolve();

    expect(screen.queryByTestId('drift-banner')).toBeNull();
  });

  it('renders banner with drift count when 1+ views drift', async () => {
    const views = [savedView('v1', 'Alpha'), savedView('v2', 'Beta'), savedView('v3', 'Gamma')];
    googleAdsDashboardMock.verifyGoogleAdsSavedView.mockImplementation((id: string) => {
      if (id === 'v2') {
        return Promise.resolve(driftVerify(id, 'Beta'));
      }
      return Promise.resolve(cleanVerify(id, id.toUpperCase()));
    });

    render(<ReportsTabSection initialSavedViews={views} />);

    const banner = await screen.findByTestId('drift-banner');
    expect(banner).toBeInTheDocument();
    expect(banner.textContent).toContain('1 saved view(s)');
    expect(banner.textContent).toContain('Beta');
  });

  it('banner dismissible', async () => {
    const views = [savedView('v1', 'Alpha')];
    googleAdsDashboardMock.verifyGoogleAdsSavedView.mockResolvedValue(driftVerify('v1', 'Alpha'));

    const user = userEvent.setup();
    render(<ReportsTabSection initialSavedViews={views} />);

    const banner = await screen.findByTestId('drift-banner');
    expect(banner).toBeInTheDocument();

    const dismiss = screen.getByRole('button', { name: 'Dismiss' });
    await user.click(dismiss);

    await waitFor(() => {
      expect(screen.queryByTestId('drift-banner')).toBeNull();
    });
  });
});
