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
  previewReport: vi.fn(),
  fetchReportDiagnostics: vi.fn(),
  createReportExport: vi.fn(),
  runScheduledReportDryRun: vi.fn(),
  downloadReportExport: vi.fn(),
  updateReport: vi.fn(),
  toggleReportSchedule: vi.fn(),
  updateReportSchedule: vi.fn(),
}));

const downloadMock = vi.hoisted(() => ({
  saveBlobAsFile: vi.fn(),
}));

const toastMock = vi.hoisted(() => ({
  addToast: vi.fn(),
  removeToast: vi.fn(),
  toasts: [] as Array<{ id: number; message: string; tone: string }>,
}));

vi.mock('../../lib/phase2Api', () => ({
  getReport: phase2ApiMock.getReport,
  listReportExports: phase2ApiMock.listReportExports,
  previewReport: phase2ApiMock.previewReport,
  fetchReportDiagnostics: phase2ApiMock.fetchReportDiagnostics,
  createReportExport: phase2ApiMock.createReportExport,
  runScheduledReportDryRun: phase2ApiMock.runScheduledReportDryRun,
  downloadReportExport: phase2ApiMock.downloadReportExport,
  updateReport: phase2ApiMock.updateReport,
  toggleReportSchedule: phase2ApiMock.toggleReportSchedule,
  updateReportSchedule: phase2ApiMock.updateReportSchedule,
}));

vi.mock('../../lib/download', () => ({
  saveBlobAsFile: downloadMock.saveBlobAsFile,
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
    phase2ApiMock.previewReport.mockResolvedValue({
      report: {
        id: 'r1',
        name: 'SLB Monthly Social Report',
        template_key: 'slb_monthly_social_report',
        schema_version: 'report.v1',
        catalog_schema_version: 'reporting_catalog.v1',
      },
      generated_at: '2026-06-16T10:00:00Z',
      date_range: { date_range: 'last_month' },
      pages: [
        {
          id: 'cover',
          title: 'Cover and period',
          sections: [
            {
              id: 'cover_widgets',
              type: 'widget_group',
              widgets: [
                {
                  widget_id: 'cover_period',
                  dataset: 'content_ops',
                  type: 'report_section',
                  status: 'rendered',
                  data: { kind: 'report_section', title: 'Cover and reporting period' },
                  coverage: {
                    dataset: 'content_ops',
                    requested_start_date: '2026-05-01',
                    requested_end_date: '2026-05-31',
                    covered_start_date: '2026-05-01',
                    covered_end_date: '2026-05-31',
                    coverage_status: 'fresh',
                    history_status: 'available',
                    freshness_status: 'fresh',
                    last_successful_sync_at: null,
                    row_count: 1,
                    source_label: 'Report narrative section',
                    coverage_note: 'Report narrative section is manually authored.',
                  },
                  warnings: [],
                },
              ],
            },
          ],
        },
      ],
      coverage_summary: {
        by_status: { fresh: 1 },
        datasets: [
          {
            dataset: 'content_ops',
            statuses: { fresh: 1 },
            row_count: 1,
            covered_start_date: '2026-05-01',
            covered_end_date: '2026-05-31',
            source_label: 'Report narrative section',
            notes: ['Report narrative section is manually authored.'],
          },
        ],
      },
      warnings: [],
      blocking_reasons: [],
      export_ready: true,
      preview_hash: 'hash-1',
    });
    phase2ApiMock.fetchReportDiagnostics.mockResolvedValue({
      report: {
        id: 'r1',
        name: 'SLB Monthly Social Report',
        schema_version: 'report.v1',
        template_key: 'slb_monthly_social_report',
      },
      generated_at: '2026-06-16T10:01:00Z',
      date_range: { date_range: 'last_month' },
      datasets: [
        {
          dataset: 'content_ops',
          coverage_status: 'fresh',
          freshness_status: 'fresh',
          retained_range: { start_date: '2026-05-01', end_date: '2026-05-31' },
          row_count: 1,
          source_label: 'Report narrative section',
          last_successful_sync_at: null,
          notes: ['Report narrative section is manually authored.'],
          recommended_next_action: 'No action required.',
        },
      ],
      coverage_summary: {
        by_status: { fresh: 1 },
        datasets: [
          {
            dataset: 'content_ops',
            statuses: { fresh: 1 },
            row_count: 1,
            covered_start_date: '2026-05-01',
            covered_end_date: '2026-05-31',
            source_label: 'Report narrative section',
            notes: ['Report narrative section is manually authored.'],
          },
        ],
      },
      blocking_reasons: [],
      export_ready: true,
      preview_hash: 'hash-1',
      preview_error: null,
      source_health: {
        schema_version: 'slb_source_health.v1',
        stored_aggregate_only: true,
        no_live_provider_calls: true,
        meta_credentials: {
          credential_count: 1,
          token_status_counts: { reauth_required: 1 },
          has_valid_credential: false,
          has_reauth_required: true,
          required_scope_coverage: {
            present: ['ads_read', 'pages_show_list'],
            missing: ['business_management', 'pages_read_engagement'],
          },
          latest_validated_at: '2026-06-17T03:00:00Z',
          latest_expires_at: '2026-02-19T22:00:00Z',
        },
        meta_page_connection: {
          connection_count: 1,
          active_count: 1,
          inactive_count: 0,
          has_active_connection: true,
          required_scope_coverage: {
            present: ['pages_show_list'],
            missing: ['pages_read_engagement'],
          },
          latest_token_expires_at: null,
        },
        meta_airbyte: {
          connection_count: 1,
          active_count: 1,
          inactive_count: 0,
          last_job_status_counts: { failed: 1 },
          latest_synced_at: '2026-06-16T22:00:20Z',
          latest_completed_at: '2026-06-16T22:00:20Z',
          sanitized_error_categories: { meta_token_expired: 1 },
        },
        stored_assets: {
          ad_account_count: 1,
          meta_page_count: 1,
          analyzable_page_count: 1,
          selected_default_page_count: 1,
        },
        stored_rows: {
          paid_meta_ads: { row_count: 21 },
          organic_facebook_page: { row_count: 0 },
          organic_facebook_posts: { row_count: 0, post_count: 0 },
          content_ops: { row_count: 0 },
        },
        recommended_next_actions: [
          'Reconnect Meta OAuth credentials before running fresh Facebook/Meta reporting.',
          'Backfill Facebook Page Insights stored rows for the fixed SLB Page/date range.',
        ],
      },
      export_history: [],
    });
    phase2ApiMock.runScheduledReportDryRun.mockResolvedValue({
      id: 'job-dry-run',
      report_id: 'r1',
      export_format: 'pdf',
      status: 'queued',
      artifact_path: '',
      error_message: '',
      metadata: { delivery_status: { mode: 'dry_run', status: 'queued', sanitized: true } },
      completed_at: null,
      created_at: '2026-06-16T10:00:00Z',
      updated_at: '2026-06-16T10:00:00Z',
    });
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

  it('downloads a completed export artifact', async () => {
    const blob = new Blob(['campaign,spend']);
    phase2ApiMock.listReportExports.mockResolvedValue([
      {
        id: 'job-1',
        report_id: 'r1',
        export_format: 'csv',
        status: 'completed',
        artifact_path: '/exports/job-1.csv',
        error_message: '',
        metadata: {},
        completed_at: '2026-01-01T01:00:00Z',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T01:00:00Z',
      },
    ]);
    phase2ApiMock.downloadReportExport.mockResolvedValue({
      blob,
      filename: 'pilot-report.csv',
    });

    renderPage();
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Download' })).toBeInTheDocument(),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Download' }));

    await waitFor(() => expect(phase2ApiMock.downloadReportExport).toHaveBeenCalledWith('job-1'));
    expect(downloadMock.saveBlobAsFile).toHaveBeenCalledWith(blob, 'pilot-report.csv');
  });

  it('shows the sanitized failure reason for a failed export job', async () => {
    phase2ApiMock.listReportExports.mockResolvedValue([
      {
        id: 'job-2',
        report_id: 'r1',
        export_format: 'pdf',
        status: 'failed',
        artifact_path: '',
        error_message: 'Export generation failed (FileNotFoundError).',
        metadata: {},
        completed_at: '2026-01-01T01:00:00Z',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T01:00:00Z',
      },
    ]);

    renderPage();

    await waitFor(() =>
      expect(screen.getByText('Export generation failed (FileNotFoundError).')).toBeInTheDocument(),
    );
    expect(screen.queryByRole('button', { name: 'Download' })).not.toBeInTheDocument();
  });

  it('renders report.v1 preview pages and coverage notes', async () => {
    phase2ApiMock.getReport.mockResolvedValue({
      ...mockReport,
      name: 'SLB Monthly Social Report',
      layout: { schema_version: 'report.v1' },
    });

    renderPage();

    expect(await screen.findByText('Coverage and export readiness')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Cover and period' })).toBeInTheDocument();
    expect(screen.getAllByText('Report narrative section is manually authored.').length).toBeGreaterThan(
      0,
    );
    expect(phase2ApiMock.previewReport).toHaveBeenCalledWith('r1');
    expect(phase2ApiMock.fetchReportDiagnostics).toHaveBeenCalledWith('r1');
    expect(screen.getByText('Stored data and delivery readiness')).toBeInTheDocument();
    expect(screen.getByText('Source health')).toBeInTheDocument();
    expect(screen.getByText('Ready to export')).toBeInTheDocument();
    expect(screen.getByText('Make this report pull real Facebook and Meta Ads data')).toBeInTheDocument();
    const metaSetupLinks = screen.getAllByRole('link', { name: 'Open Meta setup' });
    expect(metaSetupLinks.length).toBeGreaterThanOrEqual(1);
    for (const link of metaSetupLinks) {
      expect(link).toHaveAttribute(
        'href',
        '/dashboards/data-sources?sources=social&returnTo=%2Freports%2Fr1',
      );
    }
    expect(screen.getAllByText('Stored rows').length).toBeGreaterThan(0);
    expect(screen.getByText('meta reauth needed')).toBeInTheDocument();
    expect(screen.getByText(/paid 21; organic page 0; posts 0; content 0/)).toBeInTheDocument();
    expect(
      screen.getAllByText(
        'Reconnect Meta OAuth credentials before running fresh Facebook/Meta reporting.',
      ).length,
    ).toBeGreaterThan(0);
  });

  it('shows missing-history widget coverage as export blocked', async () => {
    phase2ApiMock.getReport.mockResolvedValue({
      ...mockReport,
      name: 'SLB Monthly Social Report',
      layout: { schema_version: 'report.v1' },
    });
    const previewPayload = await phase2ApiMock.previewReport();
    phase2ApiMock.previewReport.mockResolvedValue({
      ...previewPayload,
      coverage_summary: {
        by_status: { missing_history: 1 },
        datasets: [
          {
            dataset: 'organic_facebook_page',
            statuses: { missing_history: 1 },
            row_count: 0,
            covered_start_date: null,
            covered_end_date: null,
            source_label: 'Facebook Page Insights stored rows',
            notes: ['Facebook Page Insights stored rows has no retained rows for the requested range.'],
          },
        ],
      },
      export_ready: false,
      blocking_reasons: [
        'organic_facebook_page has 1 widget(s) with blocking coverage_status missing_history.',
      ],
      pages: [
        {
          id: 'organic',
          title: 'Organic Facebook/Page performance',
          sections: [
            {
              id: 'organic_widgets',
              type: 'widget_group',
              widgets: [
                {
                  ...previewPayload.pages[0].sections[0].widgets[0],
                  widget_id: 'organic_engagement_trend',
                  dataset: 'organic_facebook_page',
                  type: 'line_chart',
                  status: 'rendered',
                  data: {
                    title: 'Organic engagement trend',
                    rows: [],
                    x: 'date',
                  },
                  coverage: {
                    dataset: 'organic_facebook_page',
                    requested_start_date: '2026-05-01',
                    requested_end_date: '2026-05-31',
                    covered_start_date: null,
                    covered_end_date: null,
                    coverage_status: 'missing_history',
                    history_status: 'missing_history',
                    freshness_status: 'missing_history',
                    last_successful_sync_at: null,
                    row_count: 0,
                    source_label: 'Facebook Page Insights stored rows',
                    coverage_note:
                      'Facebook Page Insights stored rows has no retained rows for the requested range.',
                  },
                  warnings: [],
                },
              ],
            },
          ],
        },
      ],
    });

    renderPage();

    expect((await screen.findAllByText('export blocked')).length).toBeGreaterThan(0);
    expect(screen.getByText('Needs source data')).toBeInTheDocument();
    expect(await screen.findByText('Organic Facebook/Page performance')).toBeInTheDocument();
    expect(screen.getAllByText('missing_history').length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText('rendered')).not.toBeInTheDocument();
    expect(screen.queryByText('export ready')).not.toBeInTheDocument();
    expect(screen.getAllByText(/organic_facebook_page has 1 widget/).length).toBeGreaterThan(0);
  });

  it('does not repeat data table widget titles inside the table chrome', async () => {
    phase2ApiMock.getReport.mockResolvedValue({
      ...mockReport,
      name: 'SLB Monthly Social Report',
      layout: { schema_version: 'report.v1' },
    });
    const previewPayload = await phase2ApiMock.previewReport();
    phase2ApiMock.previewReport.mockResolvedValue({
      ...previewPayload,
      pages: [
        {
          id: 'top_posts',
          title: 'Top posts',
          sections: [
            {
              id: 'top_posts_widgets',
              type: 'widget_group',
              widgets: [
                {
                  ...previewPayload.pages[0].sections[0].widgets[0],
                  widget_id: 'top_posts_table',
                  dataset: 'organic_facebook_page',
                  type: 'data_table',
                  status: 'rendered',
                  data: {
                    title: 'Top posts table',
                    columns: ['post', 'post_impressions'],
                    rows: [{ post: 'Launch update', post_impressions: 1200 }],
                  },
                },
              ],
            },
          ],
        },
      ],
    });

    renderPage();

    expect(await screen.findByRole('heading', { name: 'Top posts table' })).toBeInTheDocument();
    expect(screen.getAllByRole('heading', { name: 'Top posts table' })).toHaveLength(1);
    expect(screen.queryByText('Top posts table table')).not.toBeInTheDocument();
  });

  it('shows latest export snapshot hash and diagnostics evidence', async () => {
    phase2ApiMock.getReport.mockResolvedValue({
      ...mockReport,
      name: 'SLB Monthly Social Report',
      layout: { schema_version: 'report.v1' },
    });
    phase2ApiMock.listReportExports.mockResolvedValue([
      {
        id: 'job-1',
        report_id: 'r1',
        export_format: 'pdf',
        status: 'completed',
        artifact_path: '/exports/job-1.pdf',
        error_message: '',
        metadata: {
          delivery_status: { mode: 'dry_run', status: 'rendered', sanitized: true },
          report_preview: {
            report_snapshot: {
              generated_at: '2026-06-16T10:00:00Z',
              preview_hash: 'hash-1',
              coverage_summary: { by_status: { fresh: 1 }, datasets: [] },
            },
          },
        },
        completed_at: '2026-06-16T10:01:00Z',
        created_at: '2026-06-16T10:00:00Z',
        updated_at: '2026-06-16T10:01:00Z',
      },
    ]);
    phase2ApiMock.fetchReportDiagnostics.mockResolvedValue({
      ...(await phase2ApiMock.fetchReportDiagnostics()),
      export_history: [
        {
          id: 'job-1',
          format: 'pdf',
          status: 'completed',
          created_at: '2026-06-16T10:00:00Z',
          completed_at: '2026-06-16T10:01:00Z',
          preview_hash: 'hash-1',
          delivery_status: 'rendered',
          blocking_reasons: [],
        },
      ],
    });

    renderPage();

    expect(await screen.findByText('Reproducibility')).toBeInTheDocument();
    expect(screen.getByText('matches preview')).toBeInTheDocument();
    expect(screen.getAllByText('hash-1').length).toBeGreaterThan(0);
    expect(screen.getByText('Recent export evidence')).toBeInTheDocument();
    expect(screen.getAllByText('rendered').length).toBeGreaterThan(0);
  });

  it('runs a scheduled dry-run for report.v1 schedules', async () => {
    phase2ApiMock.getReport.mockResolvedValue({
      ...mockReport,
      name: 'SLB Monthly Social Report',
      layout: { schema_version: 'report.v1' },
      schedule_enabled: true,
    });

    renderPage();

    const dryRunButton = await screen.findByRole('button', { name: /test scheduled delivery/i });
    await userEvent.click(dryRunButton);

    await waitFor(() =>
      expect(phase2ApiMock.runScheduledReportDryRun).toHaveBeenCalledWith('r1', 'pdf'),
    );
    expect(toastMock.addToast).toHaveBeenCalledWith('Scheduled dry-run queued', 'success');
  });

  it('disables report.v1 export actions when preview is blocked', async () => {
    phase2ApiMock.getReport.mockResolvedValue({
      ...mockReport,
      name: 'SLB Monthly Social Report',
      layout: { schema_version: 'report.v1' },
    });
    phase2ApiMock.previewReport.mockResolvedValue({
      ...(await phase2ApiMock.previewReport()),
      export_ready: false,
      blocking_reasons: ['coverage_policy require_full_coverage blocks coverage_status missing_history.'],
    });

    renderPage();

    const csvButton = await screen.findByRole('button', { name: /generate csv export/i });
    expect(csvButton).toBeDisabled();
    expect(screen.getAllByText(/require_full_coverage/).length).toBeGreaterThan(0);
  });
});
