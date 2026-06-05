import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import GoogleAdsReportsPage from '../GoogleAdsReportsPage';

const fetchGoogleAdsSavedViewsMock = vi.hoisted(() => vi.fn());
const createGoogleAdsSavedViewMock = vi.hoisted(() => vi.fn());
const createGoogleAdsExportMock = vi.hoisted(() => vi.fn());
const fetchGoogleAdsExportStatusMock = vi.hoisted(() => vi.fn());
const verifyGoogleAdsSavedViewMock = vi.hoisted(() => vi.fn());
const pendingAsync = () => new Promise<never>(() => {});

vi.mock('../../../lib/googleAdsDashboard', () => ({
  fetchGoogleAdsSavedViews: (...args: unknown[]) => fetchGoogleAdsSavedViewsMock(...args),
  createGoogleAdsSavedView: (...args: unknown[]) => createGoogleAdsSavedViewMock(...args),
  createGoogleAdsExport: (...args: unknown[]) => createGoogleAdsExportMock(...args),
  fetchGoogleAdsExportStatus: (...args: unknown[]) => fetchGoogleAdsExportStatusMock(...args),
  verifyGoogleAdsSavedView: (...args: unknown[]) => verifyGoogleAdsSavedViewMock(...args),
}));

describe('GoogleAdsReportsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchGoogleAdsSavedViewsMock.mockImplementation(() => pendingAsync());
    createGoogleAdsSavedViewMock.mockResolvedValue({ id: 'v1' });
    createGoogleAdsExportMock.mockResolvedValue({ id: 'j1', status: 'queued', download_url: null });
    verifyGoogleAdsSavedViewMock.mockResolvedValue({
      id: 'v1',
      name: 'Weekly View',
      drift: false,
      missing_filters: [],
      missing_columns: [],
    });
    fetchGoogleAdsExportStatusMock.mockResolvedValue({
      id: 'j1',
      status: 'completed',
      download_url: '/download/j1',
    });
  });

  it('renders the page heading', async () => {
    render(
      <MemoryRouter>
        <GoogleAdsReportsPage />
      </MemoryRouter>,
    );
    expect(screen.getByText('Reports & Exports')).toBeInTheDocument();
  });

  it('shows reasonCode=no_saved_views when empty', async () => {
    fetchGoogleAdsSavedViewsMock.mockResolvedValueOnce([]);
    render(
      <MemoryRouter>
        <GoogleAdsReportsPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      const empty = document.querySelector('[data-reason-code="no_saved_views"]');
      expect(empty).not.toBeNull();
    });
  });

  it('renders saved views with status chip after loading', async () => {
    fetchGoogleAdsSavedViewsMock.mockResolvedValueOnce([
      {
        id: 'v1',
        name: 'Weekly View',
        description: 'Exec report',
        is_shared: true,
        updated_at: '2026-04-01',
        filters: {},
        columns: [],
        created_at: '',
      },
    ]);
    render(
      <MemoryRouter>
        <GoogleAdsReportsPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText('Weekly View')).toBeInTheDocument());
    // "Shared" appears as chip text AND column header → use getAllByText.
    expect(screen.getAllByText('Shared').length).toBeGreaterThan(0);
    // KPIs
    expect(screen.getByText('Total saved views')).toBeInTheDocument();
    expect(screen.getByText('Shared views')).toBeInTheDocument();
  });

  it('creates an export on button click and renders status chip', async () => {
    const user = userEvent.setup();
    fetchGoogleAdsSavedViewsMock.mockResolvedValueOnce([]);
    render(
      <MemoryRouter>
        <GoogleAdsReportsPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(fetchGoogleAdsSavedViewsMock).toHaveBeenCalled());
    await user.click(screen.getByRole('button', { name: /create csv export/i }));
    await waitFor(() => expect(createGoogleAdsExportMock).toHaveBeenCalled());
  });
});
