import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import GoogleAdsReportsPage from '../GoogleAdsReportsPage';

const fetchGoogleAdsSavedViewsMock = vi.hoisted(() => vi.fn());
const createGoogleAdsSavedViewMock = vi.hoisted(() => vi.fn());
const createGoogleAdsExportMock = vi.hoisted(() => vi.fn());
const fetchGoogleAdsExportStatusMock = vi.hoisted(() => vi.fn());

vi.mock('../../../lib/googleAdsDashboard', () => ({
  fetchGoogleAdsSavedViews: (...args: unknown[]) => fetchGoogleAdsSavedViewsMock(...args),
  createGoogleAdsSavedView: (...args: unknown[]) => createGoogleAdsSavedViewMock(...args),
  createGoogleAdsExport: (...args: unknown[]) => createGoogleAdsExportMock(...args),
  fetchGoogleAdsExportStatus: (...args: unknown[]) => fetchGoogleAdsExportStatusMock(...args),
}));

describe('GoogleAdsReportsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchGoogleAdsSavedViewsMock.mockResolvedValue([]);
    createGoogleAdsSavedViewMock.mockResolvedValue({ id: 'v1' });
    createGoogleAdsExportMock.mockResolvedValue({ id: 'j1', status: 'queued', download_url: null });
    fetchGoogleAdsExportStatusMock.mockResolvedValue({ id: 'j1', status: 'complete', download_url: '/download/j1' });
  });

  it('renders the page heading', async () => {
    render(
      <MemoryRouter>
        <GoogleAdsReportsPage />
      </MemoryRouter>,
    );
    expect(screen.getByText('Reports & Exports')).toBeInTheDocument();
  });

  it('shows empty saved views message', async () => {
    render(
      <MemoryRouter>
        <GoogleAdsReportsPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText('No saved views yet.')).toBeInTheDocument());
  });

  it('renders saved views after loading', async () => {
    fetchGoogleAdsSavedViewsMock.mockResolvedValue([
      { id: 'v1', name: 'Weekly View', description: 'Exec report', is_shared: true, updated_at: '2026-04-01' },
    ]);
    render(
      <MemoryRouter>
        <GoogleAdsReportsPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText('Weekly View')).toBeInTheDocument());
  });

  it('creates an export on button click', async () => {
    const user = userEvent.setup();
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
