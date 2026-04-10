import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AuditLogPage from '../AuditLogPage';

const phase2ApiMock = vi.hoisted(() => ({
  listAuditLogs: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  listAuditLogs: phase2ApiMock.listAuditLogs,
}));

const SAMPLE_RESPONSE = {
  count: 2,
  next: null,
  previous: null,
  results: [
    {
      id: '1',
      action: 'login',
      resource_type: 'user',
      resource_id: 'u-1',
      metadata: {},
      created_at: '2026-04-01T12:00:00Z',
      user: { id: 'u-1', email: 'admin@example.com' },
    },
    {
      id: '2',
      action: 'report_created',
      resource_type: 'report_definition',
      resource_id: 'r-1',
      metadata: { name: 'Weekly' },
      created_at: '2026-04-02T08:00:00Z',
      user: null,
    },
  ],
};

describe('AuditLogPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    phase2ApiMock.listAuditLogs.mockResolvedValue(SAMPLE_RESPONSE);
  });

  it('renders audit log entries', async () => {
    render(<AuditLogPage />);

    await waitFor(() => expect(phase2ApiMock.listAuditLogs).toHaveBeenCalled());
    expect(screen.getByRole('heading', { name: 'Audit Log' })).toBeInTheDocument();
    expect(screen.getByText('login')).toBeInTheDocument();
    expect(screen.getByText('admin@example.com')).toBeInTheDocument();
  });

  it('shows empty state when no events match', async () => {
    phase2ApiMock.listAuditLogs.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });

    render(<AuditLogPage />);

    await waitFor(() => expect(phase2ApiMock.listAuditLogs).toHaveBeenCalled());
    expect(screen.getByText('No audit events')).toBeInTheDocument();
  });

  it('shows error state when fetch fails', async () => {
    phase2ApiMock.listAuditLogs.mockRejectedValue(new Error('Forbidden'));

    render(<AuditLogPage />);

    await waitFor(() => expect(phase2ApiMock.listAuditLogs).toHaveBeenCalled());
    expect(screen.getByText('Audit logs unavailable')).toBeInTheDocument();
    expect(screen.getByText('Forbidden')).toBeInTheDocument();
  });

  it('renders pagination controls', async () => {
    render(<AuditLogPage />);

    await waitFor(() => expect(phase2ApiMock.listAuditLogs).toHaveBeenCalled());
    expect(screen.getByRole('button', { name: /previous/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument();
    expect(screen.getByText(/page 1 of 1/i)).toBeInTheDocument();
  });

  it('renders date range inputs', async () => {
    render(<AuditLogPage />);

    await waitFor(() => expect(phase2ApiMock.listAuditLogs).toHaveBeenCalled());
    expect(screen.getByLabelText(/start date/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/end date/i)).toBeInTheDocument();
  });

  it('renders CSV export button', async () => {
    render(<AuditLogPage />);

    await waitFor(() => expect(phase2ApiMock.listAuditLogs).toHaveBeenCalled());
    expect(screen.getByRole('button', { name: /export csv/i })).toBeInTheDocument();
  });

  it('passes date params to listAuditLogs', async () => {
    render(<AuditLogPage />);

    await waitFor(() => expect(phase2ApiMock.listAuditLogs).toHaveBeenCalled());
    const callArgs = phase2ApiMock.listAuditLogs.mock.calls[0][0];
    expect(callArgs).toHaveProperty('start_date');
    expect(callArgs).toHaveProperty('end_date');
    expect(callArgs).toHaveProperty('page', 1);
  });
});
