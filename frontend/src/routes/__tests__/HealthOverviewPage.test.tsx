import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import HealthOverviewPage from '../HealthOverviewPage';

const phase2ApiMock = vi.hoisted(() => ({
  fetchHealthOverview: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  fetchHealthOverview: phase2ApiMock.fetchHealthOverview,
}));

describe('HealthOverviewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders health cards when data is available', async () => {
    phase2ApiMock.fetchHealthOverview.mockResolvedValue({
      generated_at: '2026-04-01T12:00:00Z',
      overall_status: 'ok',
      cards: [
        { key: 'api', http_status: 200, status: 'ok', detail: null, payload: {} },
        { key: 'airbyte', http_status: 200, status: 'ok', detail: null, payload: {} },
        { key: 'dbt', http_status: 200, status: 'ok', detail: null, payload: {} },
        { key: 'timezone', http_status: 200, status: 'ok', detail: null, payload: {} },
      ],
    });

    render(
      <MemoryRouter>
        <HealthOverviewPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.fetchHealthOverview).toHaveBeenCalled());
    expect(screen.getByRole('heading', { name: 'Health Overview' })).toBeInTheDocument();
    expect(screen.getByText('API')).toBeInTheDocument();
    expect(screen.getByText('AIRBYTE')).toBeInTheDocument();
    expect(screen.getByText('DBT')).toBeInTheDocument();
    expect(screen.getByText('TIMEZONE')).toBeInTheDocument();
  });

  it('shows empty state when no health cards returned', async () => {
    phase2ApiMock.fetchHealthOverview.mockResolvedValue({
      generated_at: '2026-04-01T12:00:00Z',
      overall_status: 'ok',
      cards: [],
    });

    render(
      <MemoryRouter>
        <HealthOverviewPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.fetchHealthOverview).toHaveBeenCalled());
    expect(screen.getByText('No health cards')).toBeInTheDocument();
  });

  it('shows error state when fetch fails', async () => {
    phase2ApiMock.fetchHealthOverview.mockRejectedValue(new Error('Timeout'));

    render(
      <MemoryRouter>
        <HealthOverviewPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.fetchHealthOverview).toHaveBeenCalled());
    expect(screen.getByText('Health overview unavailable')).toBeInTheDocument();
    expect(screen.getByText('Timeout')).toBeInTheDocument();
  });
});
