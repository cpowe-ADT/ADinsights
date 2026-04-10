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
  updateReport: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  getReport: phase2ApiMock.getReport,
  listReportExports: phase2ApiMock.listReportExports,
  createReportExport: phase2ApiMock.createReportExport,
  updateReport: phase2ApiMock.updateReport,
}));

vi.mock('../../lib/apiClient', () => ({
  default: {},
  API_BASE_URL: '/api',
}));

const sampleReport: ReportDefinition = {
  id: 'r1',
  name: 'Test Report',
  description: 'A test report',
  filters: {},
  layout: {},
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const completedExport: ReportExportJob = {
  id: 'e1',
  report_id: 'r1',
  export_format: 'csv',
  status: 'completed',
  artifact_path: '/exports/r1/e1.csv',
  error_message: '',
  metadata: {},
  completed_at: '2026-01-01T01:00:00Z',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T01:00:00Z',
};

const pendingExport: ReportExportJob = {
  id: 'e2',
  report_id: 'r1',
  export_format: 'pdf',
  status: 'queued',
  artifact_path: '',
  error_message: '',
  metadata: {},
  completed_at: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
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
    vi.clearAllMocks();
    phase2ApiMock.getReport.mockResolvedValue(sampleReport);
    phase2ApiMock.listReportExports.mockResolvedValue([]);
  });

  it('renders report name after loading', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('Test Report')).toBeInTheDocument());
  });

  it('shows export action buttons', async () => {
    renderPage();
    await waitFor(() => expect(phase2ApiMock.getReport).toHaveBeenCalled());
    expect(screen.getByRole('button', { name: /request csv/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /request pdf/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /request png/i })).toBeInTheDocument();
  });

  it('edit button appears and enters edit mode', async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => expect(screen.getByText('Test Report')).toBeInTheDocument());

    const editButton = screen.getByRole('button', { name: /^edit$/i });
    expect(editButton).toBeInTheDocument();

    await user.click(editButton);

    // In edit mode, name input should appear with the report name pre-filled
    const nameInput = screen.getByLabelText(/report name/i);
    expect(nameInput).toBeInTheDocument();
    expect(nameInput).toHaveValue('Test Report');

    // Description textarea should appear
    const descInput = screen.getByLabelText(/report description/i);
    expect(descInput).toBeInTheDocument();
    expect(descInput).toHaveValue('A test report');

    // Save and Cancel buttons should appear
    expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
  });

  it('completed exports show a download link', async () => {
    phase2ApiMock.listReportExports.mockResolvedValue([completedExport, pendingExport]);
    renderPage();

    await waitFor(() => expect(screen.getByText('Download')).toBeInTheDocument());
    const link = screen.getByText('Download').closest('a');
    expect(link).toHaveAttribute('href', '/api/exports/e1/download/');

    // Pending export should show "Pending" instead of download
    expect(screen.getByText('Pending')).toBeInTheDocument();
  });
});
