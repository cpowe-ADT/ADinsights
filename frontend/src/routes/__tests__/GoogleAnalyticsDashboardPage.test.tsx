import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import GoogleAnalyticsDashboardPage from '../GoogleAnalyticsDashboardPage';

const webAnalyticsMocks = vi.hoisted(() => ({
  fetchGoogleAnalyticsWebRows: vi.fn(),
}));

vi.mock('../../lib/webAnalytics', () => ({
  fetchGoogleAnalyticsWebRows: webAnalyticsMocks.fetchGoogleAnalyticsWebRows,
}));

describe('GoogleAnalyticsDashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    webAnalyticsMocks.fetchGoogleAnalyticsWebRows.mockResolvedValue({
      source: 'ga4',
      status: 'ok',
      count: 2,
      rows: [
        {
          tenant_id: 'tenant-1',
          date_day: '2026-03-18',
          property_id: '123456789',
          channel_group: 'Paid Search',
          country: 'Jamaica',
          city: 'Kingston',
          campaign_name: 'Spring Launch',
          sessions: 120,
          engaged_sessions: 84,
          conversions: 7,
          purchase_revenue: 5400,
          engagement_rate: 0.7,
          conversion_rate: 0.0583,
        },
        {
          tenant_id: 'tenant-1',
          date_day: '2026-03-17',
          property_id: '123456789',
          channel_group: 'Organic Search',
          country: 'Jamaica',
          city: 'Montego Bay',
          campaign_name: 'Brand Search',
          sessions: 80,
          engaged_sessions: 56,
          conversions: 4,
          purchase_revenue: 2500,
          engagement_rate: 0.7,
          conversion_rate: 0.05,
        },
      ],
    });
  });

  it('renders GA4 summary cards and rows', async () => {
    render(
      <MemoryRouter>
        <GoogleAnalyticsDashboardPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(webAnalyticsMocks.fetchGoogleAnalyticsWebRows).toHaveBeenCalled();
    });

    expect(screen.getByRole('heading', { name: 'Google Analytics 4' })).toBeInTheDocument();
    expect(screen.getAllByText('Paid Search')).toHaveLength(2);
    expect(screen.getAllByText('Spring Launch')).toHaveLength(2);
    expect(screen.getByText('Top channel')).toBeInTheDocument();
  });
});
