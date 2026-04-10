import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import HealthOverviewPage from '../HealthOverviewPage';

const phase2ApiMock = vi.hoisted(() => ({
  fetchHealthOverview: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  fetchHealthOverview: phase2ApiMock.fetchHealthOverview,
}));

const sampleResponse = {
  generated_at: '2026-04-10T12:00:00Z',
  overall_status: 'ok' as const,
  cards: [
    { key: 'api' as const, http_status: 200, status: 'ok', detail: 'Healthy', payload: {} },
    { key: 'airbyte' as const, http_status: 200, status: 'ok', detail: 'Running', payload: {} },
    { key: 'dbt' as const, http_status: 200, status: 'ok', detail: null, payload: {} },
    { key: 'timezone' as const, http_status: 200, status: 'ok', detail: 'America/Jamaica', payload: {} },
  ],
};

describe('HealthOverviewPage', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    phase2ApiMock.fetchHealthOverview.mockResolvedValue(sampleResponse);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders status cards', async () => {
    render(
      <MemoryRouter>
        <HealthOverviewPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('API')).toBeInTheDocument();
    });

    expect(screen.getByText('AIRBYTE')).toBeInTheDocument();
    expect(screen.getByText('DBT')).toBeInTheDocument();
    expect(screen.getByText('TIMEZONE')).toBeInTheDocument();
  });

  it('shows overall status', async () => {
    render(
      <MemoryRouter>
        <HealthOverviewPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('API')).toBeInTheDocument();
    });

    // Overall status pill + 4 card status pills = 5 "ok" pills total
    const okPills = screen.getAllByText('ok');
    expect(okPills.length).toBeGreaterThanOrEqual(1);
    // The first ok pill is the overall status in the header
    expect(okPills[0].className).toContain('phase2-pill--ok');
  });

  it('refresh button works', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

    render(
      <MemoryRouter>
        <HealthOverviewPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(phase2ApiMock.fetchHealthOverview).toHaveBeenCalled();
    });

    const callsBefore = phase2ApiMock.fetchHealthOverview.mock.calls.length;
    const refreshBtn = screen.getByRole('button', { name: /refresh/i });
    await user.click(refreshBtn);

    await waitFor(() => {
      expect(phase2ApiMock.fetchHealthOverview.mock.calls.length).toBeGreaterThan(callsBefore);
    });
  });

  it('shows last refresh timestamp', async () => {
    render(
      <MemoryRouter>
        <HealthOverviewPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('last-refresh')).toBeInTheDocument();
    });

    expect(screen.getByTestId('last-refresh').textContent).toMatch(/auto-refresh every 30s/);
  });
});
