import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AuditLogPage from '../AuditLogPage';

const phase2ApiMock = vi.hoisted(() => ({
  listAuditLogs: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  listAuditLogs: phase2ApiMock.listAuditLogs,
}));

vi.mock('../../lib/format', () => ({
  formatRelativeTime: (v: string) => `rel(${v})`,
  formatAbsoluteTime: (v: string) => `abs(${v})`,
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <AuditLogPage />
    </MemoryRouter>,
  );
}

const auditPayload = {
  count: 2,
  next: null,
  previous: null,
  results: [
    {
      id: 'log1',
      action: 'report_created',
      resource_type: 'report_definition',
      resource_id: 'rpt-1',
      metadata: { name: 'Weekly report' },
      created_at: '2026-04-01T10:00:00Z',
      user: { id: 'u1', email: 'admin@example.com' },
    },
    {
      id: 'log2',
      action: 'alert_deleted',
      resource_type: 'alert_rule',
      resource_id: 'alt-1',
      metadata: {},
      created_at: '2026-04-01T11:00:00Z',
      user: null,
    },
  ],
};

describe('AuditLogPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders audit log table with entries', async () => {
    phase2ApiMock.listAuditLogs.mockResolvedValue(auditPayload);

    renderPage();

    expect(await screen.findByText('report_created')).toBeInTheDocument();
    expect(screen.getByText('alert_deleted')).toBeInTheDocument();
    expect(screen.getByText('admin@example.com')).toBeInTheDocument();
    expect(screen.getByText('System')).toBeInTheDocument();
    expect(screen.getByText('Showing 2 of 2 events.')).toBeInTheDocument();
  });

  it('shows empty state when no events', async () => {
    phase2ApiMock.listAuditLogs.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });

    renderPage();

    expect(await screen.findByText('No audit events')).toBeInTheDocument();
  });

  it('shows error state when API fails', async () => {
    phase2ApiMock.listAuditLogs.mockRejectedValue(new Error('Forbidden'));

    renderPage();

    expect(await screen.findByText('Audit logs unavailable')).toBeInTheDocument();
    expect(screen.getByText('Forbidden')).toBeInTheDocument();
  });

  it('refresh button reloads data', async () => {
    phase2ApiMock.listAuditLogs.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });

    renderPage();

    await screen.findByText('No audit events');

    phase2ApiMock.listAuditLogs.mockResolvedValue(auditPayload);

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Refresh' }));

    expect(await screen.findByText('report_created')).toBeInTheDocument();
  });

  it('displays metadata as JSON', async () => {
    phase2ApiMock.listAuditLogs.mockResolvedValue(auditPayload);

    renderPage();

    await screen.findByText('report_created');
    expect(screen.getByText(/\"name\": \"Weekly report\"/)).toBeInTheDocument();
  });

  it('retry action reloads after error', async () => {
    phase2ApiMock.listAuditLogs.mockRejectedValueOnce(new Error('fail'));

    renderPage();

    await screen.findByText('Audit logs unavailable');

    phase2ApiMock.listAuditLogs.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Retry' }));

    expect(await screen.findByText('No audit events')).toBeInTheDocument();
  });
});
