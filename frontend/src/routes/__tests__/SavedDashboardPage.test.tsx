import '@testing-library/jest-dom';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import SavedDashboardPage from '../SavedDashboardPage';
import { serializeFilterQueryParams } from '../../lib/dashboardFilters';
import * as dashboardTemplatesModule from '../../lib/dashboardTemplates';

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
    // FP-SAVED-01: normalizeFilters now maps the platforms field; the fixture has no
    // platforms key, so fallback.platforms ([]) is used.
    // clientId also comes from fallback defaults (empty string).
    const expectedFilters = {
      dateRange: '90d' as const,
      customRange: { start: '2026-01-01', end: '2026-03-30' },
      accountId: 'act_697812007883214',
      channels: ['Meta Ads'],
      campaignQuery: 'Debt Reset',
      clientId: '',
      platforms: [],
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
    // S4c flake fix — wrap the location.search assertion in waitFor. In the
    // full-suite run the react-router navigate() commit can land a tick after
    // the setFilters call (cross-file mock-order pollution from ~113 earlier
    // suites delays the MemoryRouter history reducer's flush), producing an
    // empty search on the first probe read. In isolation both commit on the
    // same frame. Awaiting the router update is invariant to execution order
    // and leaves FP-SAVED-01/02 contracts untouched (no production-code edit;
    // the seed-once + normalizeFilters paths in SavedDashboardPage.tsx
    // remain asserted verbatim via the setFilters waitFor above).
    await waitFor(() =>
      expect(screen.getByTestId('location-search')).toHaveTextContent(
        `?${serializeFilterQueryParams(expectedFilters)}`,
      ),
    );
  });

  it('renders the SavedDashboardSlotGrid instead of the full-page template when template.layout.slots is populated', async () => {
    // S4c regression — ensure the backward-compat slot-grid hook fires when
    // (and only when) a template carries `layout.slots`. All shipped Sprint 4
    // templates have `layout` absent, so this path is exercised via a spy.
    const baseTemplate = dashboardTemplatesModule.getDashboardTemplate('meta_creative_insights');
    const spy = vi
      .spyOn(dashboardTemplatesModule, 'getDashboardTemplate')
      .mockReturnValue({
        ...baseTemplate,
        layout: {
          slots: [
            { id: 'slot-kpi', kind: 'kpi-strip', cols: 12, rows: 1, title: 'KPI strip' },
            { id: 'slot-table', kind: 'data-table', cols: 12, rows: 3, title: 'Leaderboard' },
          ],
        },
      });

    render(
      <MemoryRouter initialEntries={['/dashboards/saved/dash-1']}>
        <Routes>
          <Route path="/dashboards/saved/:dashboardId" element={<SavedDashboardPage />} />
        </Routes>
      </MemoryRouter>,
    );

    // Slot grid renders instead of the mocked "Creative dashboard body".
    expect(await screen.findByRole('region', { name: 'KPI strip' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Leaderboard' })).toBeInTheDocument();
    expect(screen.queryByText('Creative dashboard body')).not.toBeInTheDocument();

    spy.mockRestore();
  });
});
