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
    const statusMessage = screen.getByText(/Live warehouse metrics/i);
    expect(statusMessage).toHaveAttribute('aria-live', 'polite');
  });

  it('toggles to demo mode when both datasets are available', async () => {
    render(<DatasetToggle />);

    fireEvent.click(screen.getByRole('button', { name: /Use demo data/i }));

    expect(screen.getByRole('button', { name: /Use live data/i })).toBeInTheDocument();
    expect(screen.getByText(/Demo dataset loaded/i)).toBeInTheDocument();
  });

  it('suppresses the generic unavailable fallback when a specific live error is known', () => {
    useDatasetStore.setState(
      {
        ...useDatasetStore.getState(),
        mode: 'live',
        status: 'loaded',
        adapters: ['demo'],
        error: 'Live reporting is not enabled in this environment.',
        source: undefined,
      },
      true,
    );

    render(<DatasetToggle />);

    expect(screen.getByText('Live reporting is not enabled in this environment.')).toBeInTheDocument();
    expect(screen.queryByText('Dataset unavailable. Results may be empty.')).not.toBeInTheDocument();
  });

  it('describes direct Meta sync when that is the active live source', () => {
    useDatasetStore.setState(
      {
        ...useDatasetStore.getState(),
        mode: 'live',
        status: 'loaded',
        adapters: ['meta_direct', 'demo'],
        error: undefined,
        source: 'meta_direct',
      },
      true,
    );

    render(<DatasetToggle />);

    expect(
      screen.getByText(
        'Direct Meta sync data is active. Warehouse reporting is unavailable or not ready in this environment.',
      ),
    ).toBeInTheDocument();
  });
});
