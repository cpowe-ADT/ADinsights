import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import GoogleAdsConversionsPage from '../GoogleAdsConversionsPage';

const fetchGoogleAdsListMock = vi.hoisted(() => vi.fn());

vi.mock('../../../lib/googleAdsDashboard', () => ({
  fetchGoogleAdsList: (...args: unknown[]) => fetchGoogleAdsListMock(...args),
}));

vi.mock('../../../lib/apiClient', () => ({
  appendQueryParams: (endpoint: string) => endpoint,
}));

describe('GoogleAdsConversionsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchGoogleAdsListMock.mockResolvedValue({ count: 1, results: [{ action: 'Purchase', conversions: 42, value: 3200 }] });
  });

  it('renders the page heading', () => {
    render(
      <MemoryRouter>
        <GoogleAdsConversionsPage />
      </MemoryRouter>,
    );
    expect(screen.getByText('Conversions & Attribution')).toBeInTheDocument();
  });

  it('renders data rows after loading', async () => {
    render(
      <MemoryRouter>
        <GoogleAdsConversionsPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText('Purchase')).toBeInTheDocument());
  });
});
