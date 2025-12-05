import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DatasetToggle from '../DatasetToggle';
import useDashboardStore from '../../state/useDashboardStore';
import { useDatasetStore } from '../../state/useDatasetStore';

describe('DatasetToggle', () => {
  const originalDashboardState = useDashboardStore.getState();
  const originalDatasetState = useDatasetStore.getState();

  beforeEach(() => {
    useDashboardStore.setState(
      {
        ...originalDashboardState,
        activeTenantId: 'test-tenant',
        loadAll: vi.fn(),
      },
      true,
    );
    useDatasetStore.setState(
      {
        ...originalDatasetState,
        mode: 'live',
        status: 'loaded',
        adapters: ['warehouse', 'demo'],
        error: undefined,
        source: 'warehouse',
        demoTenants: [{ id: 'test-tenant', label: 'Test Tenant' }],
        demoTenantId: 'test-tenant',
      },
      true,
    );
  });

  it('announces live mode by default', () => {
    render(<DatasetToggle />);

    expect(screen.getByText(/Live data/i)).toBeInTheDocument();
    expect(screen.getByRole('status').textContent).toContain('Live warehouse metrics');
  });

  it('toggles to demo mode when both datasets are available', async () => {
    render(<DatasetToggle />);

    fireEvent.click(screen.getByRole('button', { name: /Use demo data/i }));

    expect(screen.getByRole('button', { name: /Use live data/i })).toBeInTheDocument();
    expect(screen.getByRole('status').textContent).toContain('Demo dataset loaded');
  });
});
