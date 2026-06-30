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
  fetchReportDataAvailability: vi.fn(),
}));

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => authMock,
}));

vi.mock('../../lib/phase2Api', () => ({
  listReports: phase2ApiMock.listReports,
  createSlbMonthlyReportTemplate: phase2ApiMock.createSlbMonthlyReportTemplate,
  fetchReportDataAvailability: phase2ApiMock.fetchReportDataAvailability,
}));

const LocationProbe = () => {
  const location = useLocation();
  return <div data-testid="location-path">{location.pathname}</div>;
};

describe('ReportsPage', () => {
  beforeEach(() => {
    authMock.user = { email: 'admin@example.com', roles: ['ADMIN'] };
    phase2ApiMock.listReports.mockResolvedValue([]);
    phase2ApiMock.fetchReportDataAvailability.mockResolvedValue({
      schema_version: 'report_data_availability.v1',
      stored_aggregate_only: true,
      no_live_provider_calls: true,
      template: {
        template_key: 'slb_monthly_social_report',
        label: 'SLB monthly social report',
        version: '1',
        supported_datasets: ['paid_meta_ads', 'organic_facebook_page', 'content_ops'],
        required_sources: ['meta_marketing_credential', 'facebook_page', 'content_ops_workspace'],
        eligibility: {},
      },
      requested: {
        date_range: 'last_month',
        start_date: '2026-05-01',
        end_date: '2026-05-31',
        client_id: '',
        account_id: '',
        page_id: '',
      },
      datasets: {
        paid_meta_ads: {
          dataset: 'paid_meta_ads',
          label: 'Paid Meta Ads',
          row_count: 42,
          min_date: '2026-05-01',
          max_date: '2026-05-31',
          coverage_status: 'fresh',
          coverage_note: 'Stored rows cover the requested report range.',
          source_label: 'Stored Meta Ads rows',
          metric_availability: {
            schema_version: 'report_metric_availability.v1',
            states: ['available', 'callable_no_data', 'permission_gated', 'unsupported'],
            summary: {
              available: 3,
              callable_no_data: 1,
              permission_gated: 0,
              unsupported: 0,
            },
            metrics: [],
          },
          available_accounts: [],
        },
        organic_facebook_page: {
          dataset: 'organic_facebook_page',
          label: 'Organic Facebook Page',
          row_count: 0,
          min_date: null,
          max_date: null,
          coverage_status: 'missing_history',
          coverage_note: 'No stored rows are available for the requested report range.',
          source_label: 'Stored Facebook Page Insights rows',
          available_pages: [],
        },
        organic_facebook_posts: {
          dataset: 'organic_facebook_posts',
          label: 'Organic Facebook Top Posts',
          row_count: 0,
          min_date: null,
          max_date: null,
          coverage_status: 'missing_history',
          coverage_note: 'No stored rows are available for the requested report range.',
          source_label: 'Stored Facebook Page post rows',
          post_count: 0,
          available_pages: [],
        },
        content_ops: {
          dataset: 'content_ops',
          label: 'Content Ops',
          row_count: 0,
          min_date: null,
          max_date: null,
          coverage_status: 'missing_history',
          coverage_note: 'No stored rows are available for the requested report range.',
          source_label: 'Stored Content Ops aggregate rows',
          published_post_count: 0,
        },
      },
      blocking_datasets: ['organic_facebook_page', 'content_ops'],
      warning_datasets: [],
      eligible_for_report_export: false,
      recommended_next_actions: [],
    });
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
    expect(phase2ApiMock.fetchReportDataAvailability).toHaveBeenCalledWith({
      template_key: 'slb_monthly_social_report',
      date_range: 'last_month',
    });
    expect(screen.getByRole('link', { name: /new report/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /create slb monthly report/i })).toBeInTheDocument();
    expect(screen.getByText(/slb report source availability/i)).toBeInTheDocument();
    expect(screen.getByText(/paid meta ads/i)).toBeInTheDocument();
    expect(screen.getByText(/metrics: 3 available; 1 no data/i)).toBeInTheDocument();
    expect(screen.getByText(/organic facebook page/i)).toBeInTheDocument();
  });

  it('labels paid partial coverage as ready with warnings', async () => {
    phase2ApiMock.fetchReportDataAvailability.mockResolvedValueOnce({
      schema_version: 'report_data_availability.v1',
      stored_aggregate_only: true,
      no_live_provider_calls: true,
      template: {
        template_key: 'slb_monthly_social_report',
        label: 'SLB monthly social report',
        version: '1',
        supported_datasets: ['paid_meta_ads', 'organic_facebook_page', 'content_ops'],
        required_sources: ['meta_marketing_credential', 'facebook_page', 'content_ops_workspace'],
        eligibility: {},
      },
      requested: {
        date_range: 'custom',
        start_date: '2026-05-01',
        end_date: '2026-05-31',
        client_id: '',
        account_id: '',
        page_id: '',
      },
      datasets: {
        paid_meta_ads: {
          dataset: 'paid_meta_ads',
          label: 'Paid Meta Ads',
          row_count: 1,
          min_date: '2026-05-31',
          max_date: '2026-05-31',
          coverage_status: 'partial',
          coverage_note:
            'Stored rows cover 2026-05-31 through 2026-05-31, not the full requested range 2026-05-01 through 2026-05-31.',
          source_label: 'Stored Meta Ads rows',
          available_accounts: [],
        },
        organic_facebook_page: {
          dataset: 'organic_facebook_page',
          label: 'Organic Facebook Page',
          row_count: 2,
          min_date: '2026-05-01',
          max_date: '2026-05-31',
          coverage_status: 'fresh',
          coverage_note: 'Stored rows cover the requested report range.',
          source_label: 'Stored Facebook Page Insights rows',
          available_pages: [],
        },
        organic_facebook_posts: {
          dataset: 'organic_facebook_posts',
          label: 'Organic Facebook Top Posts',
          row_count: 2,
          min_date: '2026-05-01',
          max_date: '2026-05-31',
          coverage_status: 'fresh',
          coverage_note: 'Stored rows cover the requested report range.',
          source_label: 'Stored Facebook Page post rows',
          post_count: 1,
          available_pages: [],
        },
        content_ops: {
          dataset: 'content_ops',
          label: 'Content Ops',
          row_count: 2,
          min_date: '2026-05-01',
          max_date: '2026-05-31',
          coverage_status: 'fresh',
          coverage_note: 'Stored rows cover the requested report range.',
          source_label: 'Stored Content Ops aggregate rows',
          published_post_count: 1,
        },
      },
      blocking_datasets: [],
      warning_datasets: ['paid_meta_ads'],
      eligible_for_report_export: true,
      recommended_next_actions: [],
    });

    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/ready with warnings/i)).toBeInTheDocument();
    expect(screen.getByText(/not the full requested range/i)).toBeInTheDocument();
  });

  it('surfaces a missing paid Meta credential diagnostic', async () => {
    phase2ApiMock.fetchReportDataAvailability.mockResolvedValueOnce({
      schema_version: 'report_data_availability.v1',
      stored_aggregate_only: true,
      no_live_provider_calls: true,
      template: {
        template_key: 'slb_monthly_social_report',
        label: 'SLB monthly social report',
        version: '1',
        supported_datasets: ['paid_meta_ads', 'organic_facebook_page', 'content_ops'],
        required_sources: ['meta_marketing_credential', 'facebook_page', 'content_ops_workspace'],
        eligibility: {},
      },
      requested: {
        date_range: 'custom',
        start_date: '2026-05-01',
        end_date: '2026-05-31',
        client_id: '',
        account_id: 'act_791712443035541',
        page_id: '',
      },
      datasets: {
        paid_meta_ads: {
          dataset: 'paid_meta_ads',
          label: 'Paid Meta Ads',
          row_count: 0,
          min_date: null,
          max_date: null,
          coverage_status: 'missing_history',
          coverage_note: 'No stored rows are available for the requested report range.',
          source_label: 'Stored Meta Ads rows',
          available_accounts: [
            {
              id: 'account-jdic',
              account_id: '697812007883214',
              external_id: 'act_697812007883214',
              name: 'JDIC Adtelligent Ad Account',
              currency: 'USD',
              row_count: 116,
              min_date: '2026-05-02',
              max_date: '2026-05-31',
            },
          ],
          scope_diagnostic: {
            code: 'requested_account_no_rows',
            message:
              'The requested paid Meta account has no retained rows for the selected range; other tenant Meta accounts do have retained rows.',
            required_action:
              'Reconnect Meta/Facebook, select the intended ad account, then run paid backfill.',
            available_account_count: 1,
            requested_account: {
              id: 'account-slb',
              account_id: '791712443035541',
              external_id: 'act_791712443035541',
              name: "Students' Loan Bureau (SLB)",
              currency: 'USD',
            },
            credential_status: {
              status: 'missing',
              provider: 'META',
              matched_account_id: null,
              token_status: null,
              last_validated_at: null,
            },
          },
        },
        organic_facebook_page: {
          dataset: 'organic_facebook_page',
          label: 'Organic Facebook Page',
          row_count: 0,
          min_date: null,
          max_date: null,
          coverage_status: 'missing_history',
          coverage_note: 'No stored rows are available for the requested report range.',
          source_label: 'Stored Facebook Page Insights rows',
          available_pages: [],
        },
        organic_facebook_posts: {
          dataset: 'organic_facebook_posts',
          label: 'Organic Facebook Top Posts',
          row_count: 0,
          min_date: null,
          max_date: null,
          coverage_status: 'missing_history',
          coverage_note: 'No stored rows are available for the requested report range.',
          source_label: 'Stored Facebook Page post rows',
          post_count: 0,
          available_pages: [],
        },
        content_ops: {
          dataset: 'content_ops',
          label: 'Content Ops',
          row_count: 0,
          min_date: null,
          max_date: null,
          coverage_status: 'missing_history',
          coverage_note: 'No stored rows are available for the requested report range.',
          source_label: 'Stored Content Ops aggregate rows',
          published_post_count: 0,
        },
      },
      blocking_datasets: ['paid_meta_ads'],
      warning_datasets: [],
      eligible_for_report_export: false,
      recommended_next_actions: [],
    });

    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/blocked/i)).toBeInTheDocument();
    expect(
      screen.getByText(/requested paid meta account has no retained rows/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/meta credential: missing/i)).toBeInTheDocument();
    expect(screen.getByText(/select the intended ad account/i)).toBeInTheDocument();
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
    expect(
      screen.queryByRole('button', { name: /create slb monthly report/i }),
    ).not.toBeInTheDocument();
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

    await userEvent.click(
      await screen.findByRole('button', { name: /create slb monthly report/i }),
    );

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
    const builderLinks = screen.getAllByRole('link', { name: 'Customize layout' });
    expect(builderLinks[0]).toHaveAttribute('href', '/reports/report-slb/builder');
    expect(
      screen.queryByRole('button', { name: /create slb monthly report/i }),
    ).not.toBeInTheDocument();
  });
});
