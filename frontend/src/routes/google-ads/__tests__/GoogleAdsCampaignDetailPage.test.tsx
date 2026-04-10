import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import GoogleAdsCampaignDetailPage from '../GoogleAdsCampaignDetailPage';

const fetchGoogleAdsCampaignDetailMock = vi.hoisted(() => vi.fn());

vi.mock('../../../lib/googleAdsDashboard', () => ({
  fetchGoogleAdsCampaignDetail: (...args: unknown[]) => fetchGoogleAdsCampaignDetailMock(...args),
}));

const renderPage = (campaignId = 'c123') =>
  render(
    <MemoryRouter initialEntries={[`/dashboards/google-ads/campaigns/${campaignId}`]}>
      <Routes>
        <Route path="/dashboards/google-ads/campaigns/:campaignId" element={<GoogleAdsCampaignDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );

describe('GoogleAdsCampaignDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchGoogleAdsCampaignDetailMock.mockResolvedValue({ id: 'c123', name: 'Brand Campaign', spend: 1000 });
  });

  it('renders the page heading', () => {
    renderPage();
    expect(screen.getByText('Campaign Drilldown')).toBeInTheDocument();
  });

  it('displays the campaign ID in subtitle', () => {
    renderPage();
    expect(screen.getByText(/c123/)).toBeInTheDocument();
  });

  it('renders campaign payload after loading', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText(/Brand Campaign/)).toBeInTheDocument());
  });

  it('shows error state when fetch fails', async () => {
    fetchGoogleAdsCampaignDetailMock.mockRejectedValue(new Error('Not found'));
    renderPage();
    await waitFor(() => expect(screen.getByText('Not found')).toBeInTheDocument());
  });
});
