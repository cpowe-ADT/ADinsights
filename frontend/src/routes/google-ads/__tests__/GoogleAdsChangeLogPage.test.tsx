import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import GoogleAdsChangeLogPage from '../GoogleAdsChangeLogPage';

const fetchGoogleAdsListMock = vi.hoisted(() => vi.fn());
const pendingAsync = () => new Promise<never>(() => {});

const mockFilters = { accountId: '', clientId: '', startDate: '', endDate: '', dateRange: '30d' };
vi.mock('../../../state/useDashboardStore', () => ({
  default: Object.assign(
    (selector: (state: { filters: typeof mockFilters }) => unknown) => selector({ filters: mockFilters }),
    {
      getState: () => ({ filters: mockFilters }),
    },
  ),
}));

vi.mock('../../../lib/googleAdsDashboard', () => ({
  fetchGoogleAdsList: (...args: unknown[]) => fetchGoogleAdsListMock(...args),
}));

vi.mock('../../../lib/apiClient', () => ({
  appendQueryParams: (endpoint: string) => endpoint,
}));

describe('GoogleAdsChangeLogPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchGoogleAdsListMock.mockImplementation(() => pendingAsync());
  });

  it('renders the page heading', () => {
    render(
      <MemoryRouter>
        <GoogleAdsChangeLogPage />
      </MemoryRouter>,
    );
    expect(screen.getByText('Change Log & Governance')).toBeInTheDocument();
  });

  it('renders DistributionBar + severity chips for returned rows', async () => {
    fetchGoogleAdsListMock.mockResolvedValueOnce({
      count: 3,
      page: 1,
      page_size: 50,
      num_pages: 1,
      results: [
        {
          customer_id: '123',
          change_date_time: '2026-04-14T10:00:00Z',
          user_email: 'op@example.com',
          change_resource_type: 'CAMPAIGN',
          resource_change_operation: 'CREATE',
          campaign_id: 'C1',
          changed_fields: ['status'],
        },
        {
          customer_id: '123',
          change_date_time: '2026-04-13T10:00:00Z',
          user_email: 'op@example.com',
          change_resource_type: 'AD',
          resource_change_operation: 'UPDATE',
          campaign_id: 'C2',
          changed_fields: ['budget'],
        },
        {
          customer_id: '123',
          change_date_time: '2026-04-12T10:00:00Z',
          user_email: 'op@example.com',
          change_resource_type: 'AD',
          resource_change_operation: 'REMOVE',
          campaign_id: 'C3',
          changed_fields: [],
        },
      ],
    });
    render(
      <MemoryRouter>
        <GoogleAdsChangeLogPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByTestId('google-ads-changes-section')).toBeInTheDocument());
    // KPI × 2
    expect(screen.getByText('Total changes')).toBeInTheDocument();
    expect(screen.getByText('Changes last 7 days')).toBeInTheDocument();
    // Severity chips: CREATE→info, UPDATE→warning, REMOVE→danger
    const chips = document.querySelectorAll('[data-severity]');
    const severities = Array.from(chips).map((el) => el.getAttribute('data-severity'));
    expect(severities).toContain('info');
    expect(severities).toContain('warning');
    expect(severities).toContain('danger');
  });

  it('renders reasonCode=no_change_events when empty', async () => {
    fetchGoogleAdsListMock.mockResolvedValueOnce({ count: 0, results: [] });
    render(
      <MemoryRouter>
        <GoogleAdsChangeLogPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      const empty = document.querySelector('[data-reason-code="no_change_events"]');
      expect(empty).not.toBeNull();
    });
  });

  it('preserves pagination contract by passing results verbatim (count/num_pages surfaced)', async () => {
    fetchGoogleAdsListMock.mockResolvedValueOnce({
      count: 142,
      page: 2,
      page_size: 50,
      num_pages: 3,
      results: [
        {
          customer_id: '123',
          change_date_time: '2026-04-14T10:00:00Z',
          change_resource_type: 'CAMPAIGN',
          resource_change_operation: 'UPDATE',
          campaign_id: 'C1',
        },
      ],
    });
    render(
      <MemoryRouter>
        <GoogleAdsChangeLogPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/Change log \(1\/142\)/i)).toBeInTheDocument());
  });
});
