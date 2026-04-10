import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AlertCreatePage from '../AlertCreatePage';

const phase2ApiMock = vi.hoisted(() => ({
  createAlert: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  createAlert: phase2ApiMock.createAlert,
}));

const navigateMock = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => navigateMock };
});

describe('AlertCreatePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders heading "Create Alert Rule"', () => {
    render(
      <MemoryRouter>
        <AlertCreatePage />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: 'Create Alert Rule' })).toBeInTheDocument();
  });

  it('shows form fields for Name, Metric, and Threshold', () => {
    render(
      <MemoryRouter>
        <AlertCreatePage />
      </MemoryRouter>,
    );

    expect(screen.getByLabelText('Name')).toBeInTheDocument();
    expect(screen.getByLabelText('Metric')).toBeInTheDocument();
    expect(screen.getByLabelText('Threshold')).toBeInTheDocument();
  });

  it('calls createAlert and navigates on successful submission', async () => {
    phase2ApiMock.createAlert.mockResolvedValue({
      id: 'new-alert-1',
      name: 'Test alert',
      metric: 'spend',
      comparison_operator: '>',
      threshold: '100',
      lookback_hours: 24,
      severity: 'info',
      is_active: true,
      created_at: '2026-04-10T00:00:00Z',
      updated_at: '2026-04-10T00:00:00Z',
    });

    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <AlertCreatePage />
      </MemoryRouter>,
    );

    await user.type(screen.getByLabelText('Name'), 'Test alert');
    await user.type(screen.getByLabelText('Threshold'), '100');
    await user.click(screen.getByRole('button', { name: 'Create alert' }));

    await waitFor(() => {
      expect(phase2ApiMock.createAlert).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'Test alert',
          metric: 'spend',
          comparison_operator: '>',
          threshold: '100',
          lookback_hours: 24,
          severity: 'info',
        }),
      );
    });

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith('/alerts');
    });
  });
});
