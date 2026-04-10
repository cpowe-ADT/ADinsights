import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AuditLogPage from '../AuditLogPage';

const phase2ApiMock = vi.hoisted(() => ({
  listAuditLogs: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  listAuditLogs: phase2ApiMock.listAuditLogs,
}));

describe('AuditLogPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders audit log entries', async () => {
    phase2ApiMock.listAuditLogs.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: 'log-1',
          action: 'report_created',
          resource_type: 'report_definition',
          resource_id: 'rpt-1',
          metadata: { redacted: true },
          created_at: '2026-04-01T12:00:00Z',
          user: { id: 'user-1', email: 'admin@example.com' },
        },
      ],
    });

    render(
      <MemoryRouter>
        <AuditLogPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.listAuditLogs).toHaveBeenCalled());
    expect(screen.getByRole('heading', { name: 'Audit Log' })).toBeInTheDocument();
    expect(screen.getByText('report_created')).toBeInTheDocument();
    expect(screen.getByText('report_definition')).toBeInTheDocument();
    expect(screen.getByText('admin@example.com')).toBeInTheDocument();
  });

  it('shows empty state when no events match', async () => {
    phase2ApiMock.listAuditLogs.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });

    render(
      <MemoryRouter>
        <AuditLogPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.listAuditLogs).toHaveBeenCalled());
    expect(screen.getByText('No audit events')).toBeInTheDocument();
  });

  it('shows error state when fetch fails', async () => {
    phase2ApiMock.listAuditLogs.mockRejectedValue(new Error('Forbidden'));

    render(
      <MemoryRouter>
        <AuditLogPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.listAuditLogs).toHaveBeenCalled());
    expect(screen.getByText('Audit logs unavailable')).toBeInTheDocument();
    expect(screen.getByText('Forbidden')).toBeInTheDocument();
  });
});
