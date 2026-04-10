import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ReportDetailPage from '../ReportDetailPage';

const phase2ApiMock = vi.hoisted(() => ({
  getReport: vi.fn(),
  listReportExports: vi.fn(),
  createReportExport: vi.fn(),
  toggleReportSchedule: vi.fn(),
  updateReportSchedule: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  getReport: phase2ApiMock.getReport,
  listReportExports: phase2ApiMock.listReportExports,
  createReportExport: phase2ApiMock.createReportExport,
  toggleReportSchedule: phase2ApiMock.toggleReportSchedule,
  updateReportSchedule: phase2ApiMock.updateReportSchedule,
}));

const sampleReport = {
  id: 'r1',
  name: 'Weekly Summary',
  description: 'A weekly summary report',
  filters: {},
  layout: {},
  is_active: true,
  schedule_enabled: false,
  schedule_cron: '',
  delivery_emails: [] as string[],
  last_scheduled_at: null,
  created_at: '2026-04-01T10:00:00Z',
  updated_at: '2026-04-01T10:00:00Z',
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/reports/r1']}>
      <Routes>
        <Route path="/reports/:reportId" element={<ReportDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ReportDetailPage', () => {
  beforeEach(() => {
    phase2ApiMock.getReport.mockResolvedValue({ ...sampleReport });
    phase2ApiMock.listReportExports.mockResolvedValue([]);
    phase2ApiMock.toggleReportSchedule.mockResolvedValue({ ...sampleReport, schedule_enabled: true });
    phase2ApiMock.updateReportSchedule.mockResolvedValue({ ...sampleReport });
  });

  it('renders schedule section with toggle', async () => {
    renderPage();

    await waitFor(() => expect(phase2ApiMock.getReport).toHaveBeenCalled());

    expect(screen.getByText('Scheduled delivery')).toBeInTheDocument();
    expect(screen.getByLabelText(/enable schedule/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/enable schedule/i)).not.toBeChecked();
  });

  it('schedule form shows when enabled', async () => {
    phase2ApiMock.getReport.mockResolvedValue({
      ...sampleReport,
      schedule_enabled: true,
      schedule_cron: '0 8 * * 1',
      delivery_emails: ['team@example.com'],
    });

    renderPage();

    await waitFor(() => expect(phase2ApiMock.getReport).toHaveBeenCalled());

    expect(screen.getByLabelText(/enable schedule/i)).toBeChecked();
    expect(screen.getByPlaceholderText('0 8 * * 1')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('team@example.com, boss@example.com')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /save schedule/i })).toBeInTheDocument();
  });
});
