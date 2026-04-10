import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import GoogleAdsKeywordsPage from '../GoogleAdsKeywordsPage';

const fetchGoogleAdsListMock = vi.hoisted(() => vi.fn());
const pendingAsync = () => new Promise<never>(() => {});

vi.mock('../../../lib/googleAdsDashboard', () => ({
  fetchGoogleAdsList: (...args: unknown[]) => fetchGoogleAdsListMock(...args),
}));

vi.mock('../../../lib/apiClient', () => ({
  appendQueryParams: (endpoint: string) => endpoint,
}));

describe('GoogleAdsKeywordsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchGoogleAdsListMock.mockImplementation(() => pendingAsync());
  });

  it('renders the page heading', () => {
    render(
      <MemoryRouter>
        <GoogleAdsKeywordsPage />
      </MemoryRouter>,
    );
    expect(screen.getByText('Keywords & Search Terms')).toBeInTheDocument();
  });

  it('renders mode toggle buttons', () => {
    render(
      <MemoryRouter>
        <GoogleAdsKeywordsPage />
      </MemoryRouter>,
    );
    expect(screen.getByRole('button', { name: 'Keywords' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Search Terms' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Insights' })).toBeInTheDocument();
  });

  it('switches to search terms mode on click', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <GoogleAdsKeywordsPage />
      </MemoryRouter>,
    );
    await user.click(screen.getByRole('button', { name: 'Search Terms' }));
    // Verify that fetchGoogleAdsList was called again (re-render triggers new fetch)
    await waitFor(() => expect(fetchGoogleAdsListMock).toHaveBeenCalledTimes(2));
  });
});
