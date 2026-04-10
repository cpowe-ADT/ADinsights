import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ReportDetailPage from '../ReportDetailPage';

const mockReport = {
  id: 'r1',
  name: 'Q1 Summary',
  description: 'First quarter overview',
  filters: {},
  layout: {},
  is_active: true,
  schedule_enabled: false,
  schedule_cron: '0 9 * * 1',
  delivery_emails: ['team@example.com'],
  last_scheduled_at: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const phase2ApiMock = vi.hoisted(() => ({
  getReport: vi.fn(),
  listReportExports: vi.fn(),
  createReportExport: vi.fn(),
  updateReport: vi.fn(),
  toggleReportSchedule: vi.fn(),
  updateReportSchedule: vi.fn(),
}));

const toastMock = vi.hoisted(() => ({
  addToast: vi.fn(),
  removeToast: vi.fn(),
  toasts: [] as Array<{ id: number; message: string; tone: string }>,
}));

vi.mock('../../lib/phase2Api', () => ({
  getReport: phase2ApiMock.getReport,
  listReportExports: phase2ApiMock.listReportExports,
  createReportExport: phase2ApiMock.createReportExport,
  updateReport: phase2ApiMock.updateReport,
  toggleReportSchedule: phase2ApiMock.toggleReportSchedule,
  updateReportSchedule: phase2ApiMock.updateReportSchedule,
}));

vi.mock('../../stores/useToastStore', () => ({
  useToastStore: (selector: (state: typeof toastMock) => unknown) => selector(toastMock),
}));

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/reports/r1']}>
      <Routes>
        <Route path="/reports/:reportId" element={<ReportDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ReportDetailPage inline editing', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    phase2ApiMock.getReport.mockResolvedValue({ ...mockReport });
    phase2ApiMock.listReportExports.mockResolvedValue([]);
    phase2ApiMock.updateReport.mockResolvedValue({
      ...mockReport,
      name: 'Updated Name',
      description: 'Updated Desc',
    });
  });

  it('clicking Edit shows input fields', async () => {
    renderPage();

    await waitFor(() => expect(screen.getByText('Q1 Summary')).toBeInTheDocument());

    const editButton = screen.getByRole('button', { name: /edit/i });
    await userEvent.click(editButton);

    expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/description/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
  });

  it('saving calls updateReport and shows toast', async () => {
    renderPage();

    await waitFor(() => expect(screen.getByText('Q1 Summary')).toBeInTheDocument());

    await userEvent.click(screen.getByRole('button', { name: /edit/i }));

    const nameInput = screen.getByLabelText(/name/i);
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, 'Updated Name');

    const descInput = screen.getByLabelText(/description/i);
    await userEvent.clear(descInput);
    await userEvent.type(descInput, 'Updated Desc');

    await userEvent.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => {
      expect(phase2ApiMock.updateReport).toHaveBeenCalledWith('r1', {
        name: 'Updated Name',
        description: 'Updated Desc',
      });
    });

    expect(toastMock.addToast).toHaveBeenCalledWith('Report updated');
  });

  it('cancel reverts changes', async () => {
    renderPage();

    await waitFor(() => expect(screen.getByText('Q1 Summary')).toBeInTheDocument());

    await userEvent.click(screen.getByRole('button', { name: /edit/i }));

    const nameInput = screen.getByLabelText(/name/i);
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, 'Something else');

    await userEvent.click(screen.getByRole('button', { name: /cancel/i }));

    // Should be back to read-only mode showing original name
    expect(screen.getByText('Q1 Summary')).toBeInTheDocument();
    expect(screen.queryByLabelText(/name/i)).not.toBeInTheDocument();
  });

  it('shows error toast when save fails', async () => {
    phase2ApiMock.updateReport.mockRejectedValue(new Error('Network error'));

    renderPage();

    await waitFor(() => expect(screen.getByText('Q1 Summary')).toBeInTheDocument());

    await userEvent.click(screen.getByRole('button', { name: /edit/i }));
    await userEvent.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => {
      expect(toastMock.addToast).toHaveBeenCalledWith('Failed to update', 'error');
    });
  });
});
