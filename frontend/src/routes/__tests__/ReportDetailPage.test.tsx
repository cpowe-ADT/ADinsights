import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ReportDetailPage from '../ReportDetailPage';
import type { ReportDefinition, ReportExportJob } from '../../lib/phase2Api';

const phase2ApiMock = vi.hoisted(() => ({
  getReport: vi.fn(),
  listReportExports: vi.fn(),
  createReportExport: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  getReport: phase2ApiMock.getReport,
  listReportExports: phase2ApiMock.listReportExports,
  createReportExport: phase2ApiMock.createReportExport,
}));

const sampleReport: ReportDefinition = {
  id: 'rpt-1',
  name: 'Monthly Performance Report',
  description: 'Overview of monthly ad performance',
  filters: {},
  layout: {},
  is_active: true,
  schedule_enabled: false,
  schedule_cron: '',
  delivery_emails: [],
  last_scheduled_at: null,
  created_at: '2026-04-01T10:00:00Z',
  updated_at: '2026-04-05T14:30:00Z',
};

const sampleExports: ReportExportJob[] = [
  {
    id: 'exp-1',
    report_id: 'rpt-1',
    export_format: 'csv',
    status: 'completed',
    artifact_path: '/exports/rpt-1/report.csv',
    error_message: '',
    metadata: {},
    completed_at: '2026-04-05T15:00:00Z',
    created_at: '2026-04-05T14:55:00Z',
    updated_at: '2026-04-05T15:00:00Z',
  },
  {
    id: 'exp-2',
    report_id: 'rpt-1',
    export_format: 'pdf',
    status: 'running',
    artifact_path: '',
    error_message: '',
    metadata: {},
    completed_at: null,
    created_at: '2026-04-05T15:10:00Z',
    updated_at: '2026-04-05T15:10:00Z',
  },
];

function renderPage(reportId = 'rpt-1') {
  return render(
    <MemoryRouter initialEntries={[`/reports/${reportId}`]}>
      <Routes>
        <Route path="/reports/:reportId" element={<ReportDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ReportDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    phase2ApiMock.getReport.mockResolvedValue(sampleReport);
    phase2ApiMock.listReportExports.mockResolvedValue(sampleExports);
    phase2ApiMock.createReportExport.mockResolvedValue({
      id: 'exp-3',
      report_id: 'rpt-1',
      export_format: 'png',
      status: 'queued',
      artifact_path: '',
      error_message: '',
      metadata: {},
      completed_at: null,
      created_at: '2026-04-05T15:20:00Z',
      updated_at: '2026-04-05T15:20:00Z',
    });
  });

  it('renders report name and description', async () => {
    renderPage();

    expect(await screen.findByRole('heading', { name: 'Monthly Performance Report' })).toBeInTheDocument();
    expect(screen.getByText('Overview of monthly ad performance')).toBeInTheDocument();
  });

  it('renders export action buttons for CSV, PDF, and PNG', async () => {
    renderPage();

    await screen.findByRole('heading', { name: 'Monthly Performance Report' });

    expect(screen.getByRole('button', { name: /request csv/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /request pdf/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /request png/i })).toBeInTheDocument();
  });

  it('shows export auto-polling status for running exports', async () => {
    renderPage();

    await waitFor(() => expect(phase2ApiMock.listReportExports).toHaveBeenCalled());

    const runningPill = await screen.findByText('running');
    expect(runningPill).toHaveClass('phase2-pill--running');
    expect(screen.getByText('In progress')).toBeInTheDocument();
  });

  it('displays completed export with artifact path', async () => {
    renderPage();

    await waitFor(() => expect(phase2ApiMock.listReportExports).toHaveBeenCalled());

    expect(await screen.findByText('/exports/rpt-1/report.csv')).toBeInTheDocument();
    expect(screen.getByText('completed')).toHaveClass('phase2-pill--completed');
  });

  it('creates export when format button is clicked', async () => {
    renderPage();

    await screen.findByRole('heading', { name: 'Monthly Performance Report' });

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /request png/i }));

    await waitFor(() =>
      expect(phase2ApiMock.createReportExport).toHaveBeenCalledWith('rpt-1', 'png'),
    );
  });

  it('shows empty state when no export jobs exist', async () => {
    phase2ApiMock.listReportExports.mockResolvedValue([]);

    renderPage();

    await waitFor(() => expect(screen.getByText('No export jobs yet')).toBeInTheDocument());
  });

  it('shows error state when API fails', async () => {
    phase2ApiMock.getReport.mockRejectedValue(new Error('Not found'));

    renderPage();

    await waitFor(() => expect(screen.getByText('Report unavailable')).toBeInTheDocument());
    expect(screen.getByText('Not found')).toBeInTheDocument();
  });

  it('renders back to reports link', async () => {
    renderPage();

    await screen.findByRole('heading', { name: 'Monthly Performance Report' });

    const backLink = screen.getByRole('link', { name: /back to reports/i });
    expect(backLink).toHaveAttribute('href', '/reports');
  });
});
