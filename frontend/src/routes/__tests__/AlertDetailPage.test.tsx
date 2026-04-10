import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AlertDetailPage from '../AlertDetailPage';

const phase2ApiMock = vi.hoisted(() => ({
  getAlert: vi.fn(),
  listAlertRuns: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  getAlert: phase2ApiMock.getAlert,
  listAlertRuns: phase2ApiMock.listAlertRuns,
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useParams: () => ({ alertId: 'alert-1' }) };
});

describe('AlertDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    phase2ApiMock.listAlertRuns.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  });

  it('renders alert detail', async () => {
    phase2ApiMock.getAlert.mockResolvedValue({
      id: 'alert-1',
      name: 'High CPA Alert',
      metric: 'cpa',
      comparison_operator: '>',
      threshold: 50,
      lookback_hours: 24,
      severity: 'warning',
      updated_at: '2026-04-01T10:00:00Z',
    });

    render(
      <MemoryRouter>
        <AlertDetailPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.getAlert).toHaveBeenCalled());
    expect(screen.getByRole('heading', { name: 'High CPA Alert' })).toBeInTheDocument();
  });

  it('shows error state', async () => {
    phase2ApiMock.getAlert.mockRejectedValue(new Error('Network error'));

    render(
      <MemoryRouter>
        <AlertDetailPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.getAlert).toHaveBeenCalled());
    expect(screen.getByText('Alert unavailable')).toBeInTheDocument();
  });
});
