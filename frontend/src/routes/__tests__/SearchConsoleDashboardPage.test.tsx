import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import SearchConsoleDashboardPage from '../SearchConsoleDashboardPage';

const webAnalyticsMocks = vi.hoisted(() => ({
  fetchSearchConsoleWebRows: vi.fn(),
}));

vi.mock('../../lib/webAnalytics', () => ({
  fetchSearchConsoleWebRows: webAnalyticsMocks.fetchSearchConsoleWebRows,
}));

describe('SearchConsoleDashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    webAnalyticsMocks.fetchSearchConsoleWebRows.mockResolvedValue({
      source: 'search_console',
      status: 'ok',
      count: 2,
      rows: [
        {
          date_day: '2026-04-09',
          site_url: 'https://example.com',
          country: 'JM',
          device: 'MOBILE',
          query: 'marketing analytics jamaica',
          page: '/dashboards',
          clicks: 42,
          impressions: 1200,
          ctr: 0.035,
          position: 4.2,
        },
        {
          date_day: '2026-04-08',
          site_url: 'https://example.com',
          country: 'US',
          device: 'DESKTOP',
          query: 'ad insights tool',
          page: '/home',
          clicks: 18,
          impressions: 800,
          ctr: 0.0225,
          position: 6.1,
        },
      ],
    });
  });

  it('renders heading and data rows', async () => {
    render(
      <MemoryRouter>
        <SearchConsoleDashboardPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(webAnalyticsMocks.fetchSearchConsoleWebRows).toHaveBeenCalled();
    });

    expect(screen.getByRole('heading', { name: 'Search Console' })).toBeInTheDocument();
    expect(screen.getByText('marketing analytics jamaica')).toBeInTheDocument();
    expect(screen.getByText('Total Clicks')).toBeInTheDocument();
  });

  it('shows unavailable state', async () => {
    webAnalyticsMocks.fetchSearchConsoleWebRows.mockResolvedValue({
      source: 'search_console',
      status: 'unavailable',
      count: 0,
      rows: [],
      detail: 'Search Console not configured',
    });

    render(
      <MemoryRouter>
        <SearchConsoleDashboardPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('Search Console feed unavailable')).toBeInTheDocument();
    });
  });

  it('shows empty rows state', async () => {
    webAnalyticsMocks.fetchSearchConsoleWebRows.mockResolvedValue({
      source: 'search_console',
      status: 'ok',
      count: 0,
      rows: [],
    });

    render(
      <MemoryRouter>
        <SearchConsoleDashboardPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('No Search Console rows available')).toBeInTheDocument();
    });
  });
});
