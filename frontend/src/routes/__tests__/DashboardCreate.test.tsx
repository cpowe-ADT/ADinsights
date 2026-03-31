import '@testing-library/jest-dom';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DashboardCreate from '../DashboardCreate';

const apiMocks = vi.hoisted(() => ({
  loadMetaAccounts: vi.fn(),
  fetchDashboardMetrics: vi.fn(),
  createDashboardDefinition: vi.fn(),
}));

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({
    user: { email: 'admin@example.com', roles: ['ADMIN'] },
    tenantId: 'tenant-1',
  }),
}));

vi.mock('../../lib/rbac', () => ({
  canAccessCreatorUi: () => true,
}));

vi.mock('../../lib/meta', () => ({
  loadMetaAccounts: apiMocks.loadMetaAccounts,
}));

vi.mock('../../lib/dataService', () => ({
  fetchDashboardMetrics: apiMocks.fetchDashboardMetrics,
}));

vi.mock('../../lib/phase2Api', async () => {
  const actual = await vi.importActual('../../lib/phase2Api');
  return {
    ...actual,
    createDashboardDefinition: apiMocks.createDashboardDefinition,
  };
});

vi.mock('../../components/FilterBar', () => ({
  default: ({
    state,
    onChange,
  }: {
    state: {
      dateRange: string;
      customRange: { start: string; end: string };
      accountId: string;
      channels: string[];
      campaignQuery: string;
    };
    onChange: (value: {
      dateRange: string;
      customRange: { start: string; end: string };
      accountId: string;
      channels: string[];
      campaignQuery: string;
    }) => void;
  }) => (
    <button
      type="button"
      onClick={() =>
        onChange({
          ...state,
          accountId: 'act_791712443035541',
          channels: ['Meta Ads'],
        })
      }
    >
      Choose SLB
    </button>
  ),
}));

describe('DashboardCreate', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.loadMetaAccounts.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          external_id: 'act_791712443035541',
          account_id: '791712443035541',
          name: "Students' Loan Bureau (SLB)",
        },
      ],
    });
    apiMocks.fetchDashboardMetrics.mockResolvedValue({
      campaign: {
        summary: {
          currency: 'USD',
          totalSpend: 100,
          totalReach: 1000,
          totalClicks: 50,
          averageRoas: 2.4,
          ctr: 0.05,
        },
        trend: [],
        rows: [{ id: 'cmp-1' }],
      },
      creative: [{ id: 'cr-1' }],
      budget: [{ id: 'bdg-1' }],
      parish: [],
      coverage: { startDate: '2026-01-01', endDate: '2026-03-30' },
      availability: {
        campaign: { status: 'available', reason: null },
        creative: { status: 'available', reason: null },
        budget: { status: 'available', reason: null },
        parish_map: { status: 'unavailable', reason: 'geo_unavailable' },
      },
      snapshot_generated_at: '2026-03-30T12:00:00Z',
    });
    apiMocks.createDashboardDefinition.mockResolvedValue({
      id: 'dash-1',
      name: 'SLB weekly executive overview',
      description: 'Builder output',
      template_key: 'meta_campaign_performance',
      filters: { accountId: 'act_791712443035541' },
      layout: { routeKind: 'campaigns', widgets: ['kpis'] },
      default_metric: 'spend',
      is_active: true,
      owner_email: 'admin@example.com',
      created_at: '2026-03-30T12:00:00Z',
      updated_at: '2026-03-30T12:00:00Z',
    });
  });

  it('saves a real dashboard definition and navigates to the saved-dashboard route', async () => {
    render(
      <MemoryRouter initialEntries={['/dashboards/create']}>
        <Routes>
          <Route path="/dashboards/create" element={<DashboardCreate />} />
          <Route path="/dashboards/saved/:dashboardId" element={<div>Saved dashboard route</div>} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText('Dashboard name'), {
      target: { value: 'SLB weekly executive overview' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Choose SLB' }));

    fireEvent.click(screen.getByRole('button', { name: 'Save dashboard' }));

    await waitFor(() =>
      expect(apiMocks.createDashboardDefinition).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'SLB weekly executive overview',
          template_key: 'meta_campaign_performance',
          default_metric: 'spend',
          is_active: true,
        }),
      ),
    );
    expect(await screen.findByText('Saved dashboard route')).toBeInTheDocument();
  });
});
