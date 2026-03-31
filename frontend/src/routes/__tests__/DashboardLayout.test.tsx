import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DashboardLayout from '../DashboardLayout';

const storeMock = vi.hoisted(() => ({
  state: {
    loadAll: vi.fn().mockResolvedValue(undefined),
    filters: {
      dateRange: '7d' as const,
      customRange: { start: '2026-02-13', end: '2026-02-19' },
      accountId: '',
      channels: [],
      campaignQuery: '',
    },
    setFilters: vi.fn(),
    selectedMetric: 'spend' as const,
    setSelectedMetric: vi.fn(),
    selectedParish: undefined as string | undefined,
    setSelectedParish: vi.fn(),
    campaign: {
      status: 'error' as const,
      data: undefined,
      error: 'Creative metrics invalid in aggregated response',
    },
    creative: {
      status: 'error' as const,
      data: undefined,
      error: 'Creative metrics invalid in aggregated response',
    },
    budget: {
      status: 'error' as const,
      data: undefined,
      error: 'Creative metrics invalid in aggregated response',
    },
    parish: {
      status: 'error' as const,
      data: undefined,
      error: 'Creative metrics invalid in aggregated response',
    },
    activeTenantLabel: 'Default Tenant',
    lastSnapshotGeneratedAt: undefined,
  },
}));

const authMock = vi.hoisted(() => ({
  user: { email: 'admin@example.com', roles: ['ADMIN'] },
}));

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({
    tenantId: 'tenant-1',
    logout: vi.fn(),
    user: authMock.user,
  }),
}));

vi.mock('../../components/ThemeProvider', () => ({
  useTheme: () => ({
    theme: 'light',
    toggleTheme: vi.fn(),
  }),
}));

vi.mock('../../components/ToastProvider', () => ({
  useToast: () => ({
    pushToast: vi.fn(),
  }),
}));

vi.mock('../../components/Breadcrumbs', () => ({
  default: () => <div data-testid="breadcrumbs" />,
}));

vi.mock('../../components/FilterBar', () => ({
  default: () => <div data-testid="filter-bar" />,
}));

vi.mock('../../lib/meta', () => ({
  loadMetaAccounts: vi.fn().mockResolvedValue({
    count: 0,
    next: null,
    previous: null,
    results: [],
  }),
}));

vi.mock('../../components/DatasetToggle', () => ({
  default: () => <div data-testid="dataset-toggle" />,
}));

vi.mock('../../components/TenantSwitcher', () => ({
  default: () => <div data-testid="tenant-switcher" />,
}));

vi.mock('../../components/SnapshotIndicator', () => ({
  default: () => <div data-testid="snapshot-indicator" />,
}));

vi.mock('../../state/useDashboardStore', () => ({
  default: (selector: (state: typeof storeMock.state) => unknown) => selector(storeMock.state),
}));

vi.mock('../../state/useDatasetStore', () => ({
  useDatasetStore: (selector: (state: { mode: 'live' | 'dummy'; adapters: string[] }) => unknown) =>
    selector({ mode: 'live', adapters: ['warehouse'] }),
}));

describe('DashboardLayout', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authMock.user = { email: 'admin@example.com', roles: ['ADMIN'] };
  });

  it('deduplicates repeated dashboard error messages', () => {
    render(
      <MemoryRouter initialEntries={['/dashboards/campaigns']}>
        <Routes>
          <Route path="/dashboards" element={<DashboardLayout />}>
            <Route path="campaigns" element={<div>Campaigns</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getAllByText('Creative metrics invalid in aggregated response')).toHaveLength(1);
  });

  it('hides the create nav link for viewer-only users', () => {
    authMock.user = { email: 'viewer@example.com', roles: ['VIEWER'] };

    render(
      <MemoryRouter initialEntries={['/dashboards/campaigns']}>
        <Routes>
          <Route path="/dashboards" element={<DashboardLayout />}>
            <Route path="campaigns" element={<div>Campaigns</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.queryByRole('link', { name: 'Create' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Campaigns' })).toBeInTheDocument();
  });

  it('does not overwrite saved dashboard filters from an empty route query', () => {
    storeMock.state.filters = {
      dateRange: '90d',
      customRange: { start: '2026-01-01', end: '2026-03-30' },
      accountId: 'act_697812007883214',
      channels: ['Meta Ads'],
      campaignQuery: 'Debt Reset',
    };

    render(
      <MemoryRouter initialEntries={['/dashboards/saved/dash-1']}>
        <Routes>
          <Route path="/dashboards" element={<DashboardLayout />}>
            <Route path="saved/:dashboardId" element={<div>Saved dashboard</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(storeMock.state.setFilters).not.toHaveBeenCalled();
    expect(screen.getByText('Saved dashboard')).toBeInTheDocument();
  });
});
