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

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({
    tenantId: 'tenant-1',
    logout: vi.fn(),
    user: { email: 'admin@example.com' },
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
});
