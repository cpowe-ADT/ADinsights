import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import GoogleAdsBreakdownsPage from '../GoogleAdsBreakdownsPage';

const fetchGoogleAdsListMock = vi.hoisted(() => vi.fn());

vi.mock('../../../lib/googleAdsDashboard', () => ({
  fetchGoogleAdsList: (...args: unknown[]) => fetchGoogleAdsListMock(...args),
}));

vi.mock('../../../lib/apiClient', () => ({
  appendQueryParams: (endpoint: string, query?: Record<string, unknown>) =>
    query ? `${endpoint}?dimension=${String(query.dimension)}` : endpoint,
}));

describe('GoogleAdsBreakdownsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchGoogleAdsListMock.mockResolvedValue({ count: 1, results: [{ location: 'Kingston', impressions: 5000 }] });
  });

  it('renders the page heading', () => {
    render(
      <MemoryRouter>
        <GoogleAdsBreakdownsPage />
      </MemoryRouter>,
    );
    expect(screen.getByText('Audiences, Demographics, Location, Device, Time')).toBeInTheDocument();
  });

  it('renders the dimension selector with Location default', () => {
    render(
      <MemoryRouter>
        <GoogleAdsBreakdownsPage />
      </MemoryRouter>,
    );
    const select = screen.getByLabelText('Breakdown') as HTMLSelectElement;
    expect(select.value).toBe('location');
  });

  it('changes dimension on select change', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <GoogleAdsBreakdownsPage />
      </MemoryRouter>,
    );
    await user.selectOptions(screen.getByLabelText('Breakdown'), 'device');
    expect((screen.getByLabelText('Breakdown') as HTMLSelectElement).value).toBe('device');
  });
});
