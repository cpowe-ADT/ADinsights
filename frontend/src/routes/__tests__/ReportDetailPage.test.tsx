import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ReportDetailPage from '../ReportDetailPage';

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

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useParams: () => ({ reportId: 'rpt-1' }) };
});

describe('ReportDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders report detail', async () => {
    phase2ApiMock.getReport.mockResolvedValue({
      id: 'rpt-1',
      name: 'Weekly Spend',
      description: 'Spend report',
      is_active: true,
      updated_at: '2026-04-01T10:00:00Z',
      filters: {},
      layout: {},
    });
    phase2ApiMock.listReportExports.mockResolvedValue([]);

    render(
      <MemoryRouter>
        <ReportDetailPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.getReport).toHaveBeenCalled());
    expect(screen.getByRole('heading', { name: 'Weekly Spend' })).toBeInTheDocument();
    expect(screen.getByText('No export jobs yet')).toBeInTheDocument();
  });

  it('shows error state', async () => {
    phase2ApiMock.getReport.mockRejectedValue(new Error('Network error'));
    phase2ApiMock.listReportExports.mockRejectedValue(new Error('Network error'));

    render(
      <MemoryRouter>
        <ReportDetailPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.getReport).toHaveBeenCalled());
    expect(screen.getByText('Report unavailable')).toBeInTheDocument();
  });
});
