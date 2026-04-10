import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ToastProvider } from '../../components/ToastProvider';
import AlertDetailPage from '../AlertDetailPage';

const phase2ApiMock = vi.hoisted(() => ({
  getAlert: vi.fn(),
  updateAlert: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  getAlert: phase2ApiMock.getAlert,
  updateAlert: phase2ApiMock.updateAlert,
}));

const mockAlert = {
  id: 'a1',
  name: 'Spend spike',
  metric: 'spend',
  comparison_operator: '>',
  threshold: '1000',
  lookback_hours: 24,
  severity: 'critical',
  is_active: true,
  created_at: '2026-04-01T00:00:00Z',
  updated_at: '2026-04-10T08:00:00Z',
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/alerts/a1']}>
      <ToastProvider>
        <Routes>
          <Route path="/alerts/:alertId" element={<AlertDetailPage />} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>,
  );
}

describe('AlertDetailPage', () => {
  beforeEach(() => {
    phase2ApiMock.getAlert.mockResolvedValue({ ...mockAlert });
    phase2ApiMock.updateAlert.mockResolvedValue({ ...mockAlert, is_active: false });
  });

  it('shows active/paused state with toggle button', async () => {
    renderPage();

    await waitFor(() => expect(phase2ApiMock.getAlert).toHaveBeenCalledWith('a1'));

    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument();
  });

  it('shows paused state when alert is inactive', async () => {
    phase2ApiMock.getAlert.mockResolvedValue({ ...mockAlert, is_active: false });

    renderPage();

    await waitFor(() => expect(phase2ApiMock.getAlert).toHaveBeenCalled());

    expect(screen.getByText('Paused')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Resume' })).toBeInTheDocument();
  });
});
