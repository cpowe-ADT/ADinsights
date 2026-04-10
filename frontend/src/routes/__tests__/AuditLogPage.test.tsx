import '@testing-library/jest-dom';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import AuditLogPage from '../AuditLogPage';

const phase2ApiMock = vi.hoisted(() => ({
  listAuditLogs: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  listAuditLogs: phase2ApiMock.listAuditLogs,
}));

vi.mock('../../lib/apiClient', () => ({
  API_BASE_URL: '/api',
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <AuditLogPage />
    </MemoryRouter>,
  );
}

describe('AuditLogPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    phase2ApiMock.listAuditLogs.mockResolvedValue({
      count: 1,
      results: [
        {
          id: 'log-1',
          action: 'report_created',
          resource_type: 'report_definition',
          resource_id: 'rpt-001',
          user: { email: 'admin@example.com' },
          metadata: { source: 'manual' },
          created_at: '2026-04-01T12:00:00Z',
        },
      ],
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders audit log entries', async () => {
    renderPage();

    expect(await screen.findByText('report_created')).toBeInTheDocument();
    expect(screen.getByText('admin@example.com')).toBeInTheDocument();
  });

  it('CSV export opens server-side endpoint', async () => {
    const windowOpenSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
    renderPage();

    const csvButton = await screen.findByRole('button', { name: /export csv/i });
    const user = userEvent.setup();
    await user.click(csvButton);

    expect(windowOpenSpy).toHaveBeenCalledTimes(1);
    const calledUrl = windowOpenSpy.mock.calls[0][0] as string;
    expect(calledUrl).toContain('/audit-logs/export_csv/');
    expect(windowOpenSpy.mock.calls[0][1]).toBe('_blank');
  });

  it('CSV export includes active filters in URL', async () => {
    const windowOpenSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
    const { fireEvent } = await import('@testing-library/react');

    renderPage();

    // Wait for initial load
    await screen.findByText('report_created');

    const actionInput = screen.getByPlaceholderText('e.g. report_created');

    // Change filter value - this triggers a reload
    fireEvent.change(actionInput, { target: { value: 'user_login' } });

    // Wait for reload to complete and table to re-appear
    await screen.findByRole('button', { name: /export csv/i });

    const csvButton = screen.getByRole('button', { name: /export csv/i });
    const user = userEvent.setup();
    await user.click(csvButton);

    const lastCallIndex = windowOpenSpy.mock.calls.length - 1;
    const calledUrl = windowOpenSpy.mock.calls[lastCallIndex][0] as string;
    expect(calledUrl).toContain('action=user_login');
  });
});
