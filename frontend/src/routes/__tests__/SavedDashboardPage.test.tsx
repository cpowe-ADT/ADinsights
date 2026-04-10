import '@testing-library/jest-dom';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import SavedDashboardPage from '../SavedDashboardPage';
import { serializeFilterQueryParams } from '../../lib/dashboardFilters';

const apiMocks = vi.hoisted(() => ({
  getDashboardDefinition: vi.fn(),
}));

const storeMock = vi.hoisted(() => ({
  state: {
    setFilters: vi.fn(),
    setSelectedMetric: vi.fn(),
    setSelectedParish: vi.fn(),
  },
}));

vi.mock('../../lib/phase2Api', async () => {
  const actual = await vi.importActual('../../lib/phase2Api');
  return {
    ...actual,
    getDashboardDefinition: apiMocks.getDashboardDefinition,
  };
});

vi.mock('../../state/useDashboardStore', () => ({
  default: (selector: (state: typeof storeMock.state) => unknown) => selector(storeMock.state),
}));

vi.mock('../CampaignDashboard', () => ({
  default: () => <div>Campaign dashboard body</div>,
}));

vi.mock('../CreativeDashboard', () => ({
  default: () => <div>Creative dashboard body</div>,
}));

vi.mock('../BudgetDashboard', () => ({
  default: () => <div>Budget dashboard body</div>,
}));

vi.mock('../ParishMapDetail', () => ({
  default: () => <div>Parish map body</div>,
}));

const LocationProbe = () => {
  const location = useLocation();
  return <div data-testid="location-search">{location.search}</div>;
};

describe('SavedDashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.getDashboardDefinition.mockResolvedValue({
      id: 'dash-1',
      name: 'JDIC creative review',
      description: 'Saved creative dashboard',
      template_key: 'meta_creative_insights',
      filters: {
        dateRange: '90d',
        customRange: { start: '2026-01-01', end: '2026-03-30' },
        accountId: 'act_697812007883214',
        channels: ['Meta Ads'],
        campaignQuery: 'Debt Reset',
      },
      layout: { widgets: ['creative_summary', 'creative_table'] },
      default_metric: 'ctr',
      is_active: true,
      owner_email: 'admin@example.com',
      created_at: '2026-03-30T12:00:00Z',
      updated_at: '2026-03-30T12:05:00Z',
    });
  });

  it('loads a saved definition, seeds filters, and renders the matching dashboard template', async () => {
    const expectedFilters = {
      dateRange: '90d' as const,
      customRange: { start: '2026-01-01', end: '2026-03-30' },
      accountId: 'act_697812007883214',
      channels: ['Meta Ads'],
      campaignQuery: 'Debt Reset',
    };

    render(
      <MemoryRouter initialEntries={['/dashboards/saved/dash-1']}>
        <Routes>
          <Route
            path="/dashboards/saved/:dashboardId"
            element={
              <>
                <SavedDashboardPage />
                <LocationProbe />
              </>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText('Creative dashboard body')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'JDIC creative review' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /back to library/i })).toHaveAttribute(
      'href',
      '/dashboards',
    );

    await waitFor(() =>
      expect(storeMock.state.setFilters).toHaveBeenCalledWith(expectedFilters),
    );
    expect(storeMock.state.setSelectedMetric).toHaveBeenCalledWith('ctr');
    expect(storeMock.state.setSelectedParish).toHaveBeenCalledWith(undefined);
    expect(screen.getByTestId('location-search')).toHaveTextContent(
      `?${serializeFilterQueryParams(expectedFilters)}`,
    );
  });
});
