import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import GoogleAdsChangeLogPage from '../GoogleAdsChangeLogPage';

const fetchGoogleAdsListMock = vi.hoisted(() => vi.fn());
const pendingAsync = () => new Promise<never>(() => {});

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

  it('renders data rows after loading', async () => {
    fetchGoogleAdsListMock.mockResolvedValueOnce({
      count: 1,
      results: [{ id: 'cl1', change_type: 'budget_update', timestamp: '2026-04-01' }],
    });
    render(
      <MemoryRouter>
        <GoogleAdsChangeLogPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText('budget_update')).toBeInTheDocument());
  });
});
