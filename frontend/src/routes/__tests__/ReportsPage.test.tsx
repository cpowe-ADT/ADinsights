import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ReportsPage from '../ReportsPage';

const authMock = vi.hoisted(() => ({
  user: { email: 'admin@example.com', roles: ['ADMIN'] },
}));

const phase2ApiMock = vi.hoisted(() => ({
  listReports: vi.fn(),
  createSlbMonthlyReportTemplate: vi.fn(),
}));

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => authMock,
}));

vi.mock('../../lib/phase2Api', () => ({
  listReports: phase2ApiMock.listReports,
  createSlbMonthlyReportTemplate: phase2ApiMock.createSlbMonthlyReportTemplate,
}));

const LocationProbe = () => {
  const location = useLocation();
  return <div data-testid="location-path">{location.pathname}</div>;
};

describe('ReportsPage', () => {
  beforeEach(() => {
    authMock.user = { email: 'admin@example.com', roles: ['ADMIN'] };
    phase2ApiMock.listReports.mockResolvedValue([]);
    phase2ApiMock.createSlbMonthlyReportTemplate.mockResolvedValue({
      id: 'report-slb',
      name: 'SLB Monthly Social Report',
      description: '',
      filters: {},
      layout: { schema_version: 'report.v1' },
      is_active: true,
      schedule_enabled: false,
      schedule_cron: '',
      delivery_emails: [],
      last_scheduled_at: null,
      created_at: '2026-06-16T00:00:00Z',
      updated_at: '2026-06-16T00:00:00Z',
    });
  });

  it('shows the new report action for non-viewer users', async () => {
    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.listReports).toHaveBeenCalled());
    expect(screen.getByRole('link', { name: /new report/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /create slb monthly report/i })).toBeInTheDocument();
  });

  it('hides report creation actions for viewer-only users', async () => {
    authMock.user = { email: 'viewer@example.com', roles: ['VIEWER'] };

    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.listReports).toHaveBeenCalled());
    expect(screen.queryByRole('link', { name: /new report/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /create slb monthly report/i })).not.toBeInTheDocument();
  });

  it('creates an SLB monthly report and navigates to detail', async () => {
    render(
      <MemoryRouter initialEntries={['/reports']}>
        <Routes>
          <Route
            path="/reports"
            element={
              <>
                <ReportsPage />
                <LocationProbe />
              </>
            }
          />
          <Route path="/reports/:reportId" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>,
    );

    await userEvent.click(await screen.findByRole('button', { name: /create slb monthly report/i }));

    await waitFor(() =>
      expect(phase2ApiMock.createSlbMonthlyReportTemplate).toHaveBeenCalledWith({
        name: 'SLB Monthly Social Report',
        date_range: 'last_month',
      }),
    );
    expect(screen.getByTestId('location-path')).toHaveTextContent('/reports/report-slb');
  });

  it('shows the existing SLB report first and hides duplicate creation', async () => {
    phase2ApiMock.listReports.mockResolvedValueOnce([
      {
        id: 'report-other',
        name: 'Other report',
        description: '',
        filters: {},
        layout: {},
        is_active: true,
        schedule_enabled: false,
        schedule_cron: '',
        delivery_emails: [],
        last_scheduled_at: null,
        created_at: '2026-06-16T00:00:00Z',
        updated_at: '2026-06-16T00:00:00Z',
      },
      {
        id: 'report-slb',
        name: 'SLB Monthly Social Report',
        description: '',
        filters: { template_key: 'slb_monthly_social_report' },
        layout: { schema_version: 'report.v1', template_key: 'slb_monthly_social_report' },
        is_active: true,
        schedule_enabled: false,
        schedule_cron: '',
        delivery_emails: [],
        last_scheduled_at: null,
        created_at: '2026-06-16T00:00:00Z',
        updated_at: '2026-06-17T00:00:00Z',
      },
    ]);

    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
    );

    const openSlbLinks = await screen.findAllByRole('link', { name: 'Open SLB report' });
    expect(openSlbLinks[0]).toHaveAttribute('href', '/reports/report-slb');
    expect(screen.queryByRole('button', { name: /create slb monthly report/i })).not.toBeInTheDocument();
  });
});
