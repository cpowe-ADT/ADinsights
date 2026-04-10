import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AuditLogPage from '../AuditLogPage';

const mockEntry = {
  id: 'a1',
  action: 'report_created',
  resource_type: 'report_definition',
  resource_id: 'r1',
  user: { id: 'u1', email: 'admin@example.com' },
  metadata: { key: 'value' },
  created_at: '2026-03-15T10:00:00Z',
};

const phase2ApiMock = vi.hoisted(() => ({
  listAuditLogs: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  listAuditLogs: phase2ApiMock.listAuditLogs,
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <AuditLogPage />
    </MemoryRouter>,
  );
}

describe('AuditLogPage date range filter and pagination', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    phase2ApiMock.listAuditLogs.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [mockEntry],
    });
  });

  it('date range inputs appear and filter', async () => {
    renderPage();

    await waitFor(() => expect(screen.getByText('report_created')).toBeInTheDocument());

    const startInput = screen.getByLabelText(/start date/i);
    const endInput = screen.getByLabelText(/end date/i);
    expect(startInput).toBeInTheDocument();
    expect(endInput).toBeInTheDocument();

    await userEvent.type(startInput, '2026-03-01');

    await waitFor(() => {
      const calls = phase2ApiMock.listAuditLogs.mock.calls;
      const lastCall = calls[calls.length - 1][0];
      expect(lastCall).toMatchObject({ start_date: '2026-03-01', page: 1 });
    });
  });

  it('pagination controls appear with correct page info', async () => {
    phase2ApiMock.listAuditLogs.mockResolvedValue({
      count: 40,
      next: 'http://localhost/api/audit-logs/?page=2',
      previous: null,
      results: [mockEntry],
    });

    renderPage();

    await waitFor(() => expect(screen.getByText('report_created')).toBeInTheDocument());

    expect(screen.getByText(/page 1 of 2/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /previous/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /next/i })).toBeEnabled();
  });

  it('Next/Previous buttons call API with page param', async () => {
    phase2ApiMock.listAuditLogs
      .mockResolvedValueOnce({
        count: 40,
        next: 'http://localhost/api/audit-logs/?page=2',
        previous: null,
        results: [mockEntry],
      })
      .mockResolvedValueOnce({
        count: 40,
        next: null,
        previous: 'http://localhost/api/audit-logs/?page=1',
        results: [{ ...mockEntry, id: 'a2', action: 'report_updated' }],
      });

    renderPage();

    await waitFor(() => expect(screen.getByText('report_created')).toBeInTheDocument());

    await userEvent.click(screen.getByRole('button', { name: /next/i }));

    await waitFor(() => {
      const calls = phase2ApiMock.listAuditLogs.mock.calls;
      const lastCall = calls[calls.length - 1][0];
      expect(lastCall).toMatchObject({ page: 2 });
    });

    await waitFor(() => expect(screen.getByText(/page 2 of 2/i)).toBeInTheDocument());

    await userEvent.click(screen.getByRole('button', { name: /previous/i }));

    await waitFor(() => {
      const calls = phase2ApiMock.listAuditLogs.mock.calls;
      const lastCall = calls[calls.length - 1][0];
      expect(lastCall).toMatchObject({ page: 1 });
    });
  });
});
