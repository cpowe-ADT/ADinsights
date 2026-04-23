import { render, screen, waitFor } from '@testing-library/react';
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
  const actual =
    await vi.importActual<typeof import('../../../../lib/googleAdsDashboard')>(
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
  description: 'A saved view',
  filters: {},
  columns: [],
  is_shared: true,
  created_at: '2026-04-01T00:00:00Z',
  updated_at: '2026-04-01T00:00:00Z',
});

describe('ReportsTabSection — integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    googleAdsDashboardMock.fetchGoogleAdsSavedViews.mockResolvedValue([]);
    googleAdsDashboardMock.verifyGoogleAdsSavedView.mockResolvedValue({
      id: 'x',
      name: 'x',
      drift: false,
      unknown_filter_keys: [],
      unknown_columns: [],
      checked_against_version: 'google-ads-v23',
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders loading state (no initialSavedViews, fetch pending)', async () => {
    let resolveFn: ((v: GoogleAdsSavedView[]) => void) | undefined;
    googleAdsDashboardMock.fetchGoogleAdsSavedViews.mockImplementation(
      () =>
        new Promise<GoogleAdsSavedView[]>((resolve) => {
          resolveFn = resolve;
        }),
    );
    render(<ReportsTabSection />);
    expect(screen.getByText('Loading saved views...')).toBeInTheDocument();
    resolveFn?.([]);
  });

  it('renders empty state when saved views list is empty', async () => {
    render(<ReportsTabSection initialSavedViews={[]} />);
    await waitFor(() => {
      expect(screen.getByText('No saved views yet')).toBeInTheDocument();
    });
  });

  it('renders populated state with saved view rows', async () => {
    const views = [savedView('v1', 'Alpha'), savedView('v2', 'Beta')];
    render(<ReportsTabSection initialSavedViews={views} />);
    expect(screen.getByTestId('google-ads-reports-section')).toBeInTheDocument();
    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.getByText('Beta')).toBeInTheDocument();
  });
});
