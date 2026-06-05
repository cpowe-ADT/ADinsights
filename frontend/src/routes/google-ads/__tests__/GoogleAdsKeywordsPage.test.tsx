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

const mockFilters = {
  accountId: 'cust-001',
  clientId: '',
  startDate: '',
  endDate: '',
  dateRange: '30d',
};
vi.mock('../../../state/useDashboardStore', () => ({
  default: Object.assign(
    (selector: (state: { filters: typeof mockFilters }) => unknown) =>
      selector({ filters: mockFilters }),
    {
      getState: () => ({ filters: mockFilters }),
    },
  ),
}));

const keywordFixture = {
  count: 2,
  source_engine: 'sdk',
  results: [
    {
      keyword_text: 'brand search',
      match_type: 'EXACT',
      keyword_status: 'ENABLED',
      quality_score: 8,
      impressions: 10000,
      clicks: 500,
      conversions: 20,
      cost: 250,
      cpc: 0.5,
      cpa: 12.5,
    },
    {
      keyword_text: 'competitor',
      match_type: 'BROAD',
      keyword_status: 'ENABLED',
      quality_score: 5,
      impressions: 5000,
      clicks: 100,
      conversions: 2,
      cost: 100,
      cpc: 1.0,
      cpa: 50,
    },
  ],
};

const searchTermsFixture = {
  count: 1,
  source_engine: 'sdk',
  results: [
    {
      search_term: 'buy widgets online',
      impressions: 1000,
      clicks: 50,
      conversions: 5,
      cost: 75,
      cpa: 15,
    },
  ],
};

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

  it('renders the KPI strip after loading keywords', async () => {
    // First call: keywords mode primary fetch. Second call: search_terms prefetch.
    fetchGoogleAdsListMock
      .mockResolvedValueOnce(keywordFixture)
      .mockResolvedValueOnce(searchTermsFixture);
    render(
      <MemoryRouter>
        <GoogleAdsKeywordsPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText('Search KPIs')).toBeInTheDocument());
    expect(screen.getByText('Total Keywords')).toBeInTheDocument();
    expect(screen.getByText('Avg Quality Score')).toBeInTheDocument();
    expect(screen.getByText('Top Row Conversions')).toBeInTheDocument();
  });

  it('renders Quality Score vs CPC bubble scatter in keywords mode', async () => {
    fetchGoogleAdsListMock
      .mockResolvedValueOnce(keywordFixture)
      .mockResolvedValueOnce(searchTermsFixture);
    render(
      <MemoryRouter>
        <GoogleAdsKeywordsPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(
        screen.getByRole('img', { name: /keyword quality score vs CPC/i }),
      ).toBeInTheDocument(),
    );
  });

  it('renders top 10 search terms bar in keywords mode', async () => {
    fetchGoogleAdsListMock
      .mockResolvedValueOnce(keywordFixture)
      .mockResolvedValueOnce(searchTermsFixture);
    render(
      <MemoryRouter>
        <GoogleAdsKeywordsPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText('Top 10 search terms by conversions')).toBeInTheDocument(),
    );
    await waitFor(() =>
      expect(
        screen.getByRole('img', { name: /top search terms by conversions/i }),
      ).toBeInTheDocument(),
    );
  });

  it('switches to search terms mode and re-fetches', async () => {
    fetchGoogleAdsListMock.mockResolvedValue(keywordFixture);
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <GoogleAdsKeywordsPage />
      </MemoryRouter>,
    );
    // Initial: keywords primary + search_terms prefetch = 2 calls
    await waitFor(() => expect(fetchGoogleAdsListMock).toHaveBeenCalledTimes(2));
    await user.click(screen.getByRole('button', { name: 'Search Terms' }));
    // After switch: +1 primary fetch for search_terms mode (prefetch only runs in keywords mode)
    await waitFor(() => expect(fetchGoogleAdsListMock).toHaveBeenCalledTimes(3));
  });

  it('renders EmptyState with reasonCode when no rows', async () => {
    fetchGoogleAdsListMock.mockResolvedValueOnce({ count: 0, results: [] });
    render(
      <MemoryRouter>
        <GoogleAdsKeywordsPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      const empty = document.querySelector('[data-reason-code="no_keywords"]');
      expect(empty).not.toBeNull();
    });
  });

  it('shows error state when fetch fails', async () => {
    fetchGoogleAdsListMock.mockRejectedValueOnce(new Error('Upstream timeout'));
    render(
      <MemoryRouter>
        <GoogleAdsKeywordsPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText('Upstream timeout')).toBeInTheDocument());
  });
});
