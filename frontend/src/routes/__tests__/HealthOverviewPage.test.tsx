import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import HealthOverviewPage from '../HealthOverviewPage';

const phase2ApiMock = vi.hoisted(() => ({
  fetchHealthOverview: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  fetchHealthOverview: phase2ApiMock.fetchHealthOverview,
}));

vi.mock('../../lib/format', () => ({
  formatRelativeTime: (v: string) => `rel(${v})`,
  formatAbsoluteTime: (v: string) => `abs(${v})`,
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <HealthOverviewPage />
    </MemoryRouter>,
  );
}

const overviewPayload = {
  generated_at: '2026-04-01T12:00:00Z',
  overall_status: 'ok' as const,
  cards: [
    {
      key: 'api' as const,
      http_status: 200,
      status: 'healthy',
      detail: 'All endpoints responding',
      payload: {},
    },
    {
      key: 'dbt' as const,
      http_status: 200,
      status: 'healthy',
      detail: null,
      payload: {},
    },
  ],
};

describe('HealthOverviewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders health cards with status and detail', async () => {
    phase2ApiMock.fetchHealthOverview.mockResolvedValue(overviewPayload);

    renderPage();

    expect(await screen.findByText('API')).toBeInTheDocument();
    expect(screen.getByText('DBT')).toBeInTheDocument();
    expect(screen.getByText('All endpoints responding')).toBeInTheDocument();
    expect(screen.getByText('No additional details provided.')).toBeInTheDocument();
    expect(screen.getByText('ok')).toBeInTheDocument();
  });

  it('shows empty state when no cards', async () => {
    phase2ApiMock.fetchHealthOverview.mockResolvedValue({
      generated_at: '2026-04-01T12:00:00Z',
      overall_status: 'ok',
      cards: [],
    });

    renderPage();

    expect(await screen.findByText('No health cards')).toBeInTheDocument();
  });

  it('shows error state when API fails', async () => {
    phase2ApiMock.fetchHealthOverview.mockRejectedValue(new Error('Service unavailable'));

    renderPage();

    expect(await screen.findByText('Health overview unavailable')).toBeInTheDocument();
    expect(screen.getByText('Service unavailable')).toBeInTheDocument();
  });

  it('refresh button reloads data', async () => {
    phase2ApiMock.fetchHealthOverview.mockResolvedValue({
      ...overviewPayload,
      cards: [],
    });

    renderPage();

    await screen.findByText('No health cards');

    phase2ApiMock.fetchHealthOverview.mockResolvedValue(overviewPayload);

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Refresh' }));

    expect(await screen.findByText('API')).toBeInTheDocument();
  });

  it('displays overall status pill', async () => {
    phase2ApiMock.fetchHealthOverview.mockResolvedValue({
      ...overviewPayload,
      overall_status: 'degraded',
    });

    renderPage();

    expect(await screen.findByText('degraded')).toBeInTheDocument();
  });
});
