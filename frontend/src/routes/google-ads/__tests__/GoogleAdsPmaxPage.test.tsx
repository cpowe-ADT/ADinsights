import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import GoogleAdsPmaxPage from '../GoogleAdsPmaxPage';

const getMock = vi.hoisted(() => vi.fn());
const pendingAsync = () => new Promise<never>(() => {});

vi.mock('../../../lib/apiClient', () => ({
  appendQueryParams: (endpoint: string) => endpoint,
  get: (...args: unknown[]) => getMock(...args),
}));

describe('GoogleAdsPmaxPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getMock.mockImplementation(() => pendingAsync());
  });

  it('renders the page heading', () => {
    render(
      <MemoryRouter>
        <GoogleAdsPmaxPage />
      </MemoryRouter>,
    );
    expect(screen.getByText('Performance Max')).toBeInTheDocument();
  });

  it('renders KPI strip + AssetGroupTreemap + hidden table on load', async () => {
    getMock.mockResolvedValueOnce({
      count: 3,
      results: [
        {
          asset_group_id: 'g1',
          asset_group_name: 'Launch Push',
          asset_group_status: 'ENABLED',
          spend: 5000,
          impressions: 10000,
          clicks: 200,
          conversions: 12,
          roas: 1.8,
        },
        {
          asset_group_id: 'g2',
          asset_group_name: 'Evergreen',
          asset_group_status: 'PAUSED',
          spend: 2000,
          impressions: 4000,
          clicks: 80,
          conversions: 4,
          roas: 0.9,
        },
        {
          asset_group_id: 'g3',
          asset_group_name: 'Remarket',
          asset_group_status: 'ENABLED',
          spend: 900,
          impressions: 1500,
          clicks: 30,
          conversions: 2,
          roas: 0.4,
        },
      ],
    });
    const { container } = render(
      <MemoryRouter>
        <GoogleAdsPmaxPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText('Total Asset Groups')).toBeInTheDocument());
    expect(screen.getByText('Total Cost')).toBeInTheDocument();
    expect(screen.getByText('Total Conv')).toBeInTheDocument();

    // Treemap renders with role="img" + sr-only accessible table.
    expect(screen.getByRole('img', { name: /performance max asset groups/i })).toBeInTheDocument();

    // Hidden-table equivalent lists every asset group.
    const treemapTable = container.querySelector(
      'table.sr-only[aria-label="Performance Max asset groups by spend"]',
    );
    expect(treemapTable).toBeInTheDocument();
    expect(treemapTable?.querySelectorAll('tbody tr').length).toBe(3);

    // Low-ROAS hatch pattern for non-color encoding.
    expect(container.querySelector('#viz-treemap-hatch')).toBeInTheDocument();
  });

  it('shows empty state with reasonCode when no groups', async () => {
    getMock.mockResolvedValueOnce({ count: 0, results: [] });
    const { container } = render(
      <MemoryRouter>
        <GoogleAdsPmaxPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(container.querySelector('[data-reason-code="no_pmax_groups"]')).toBeInTheDocument(),
    );
  });

  it('shows error state when fetch fails', async () => {
    getMock.mockRejectedValueOnce(new Error('PMax boom'));
    render(
      <MemoryRouter>
        <GoogleAdsPmaxPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText('PMax boom')).toBeInTheDocument());
  });
});
