import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ReportLayoutPreview from '../ReportLayoutPreview';

const phase2ApiMock = vi.hoisted(() => ({
  getReport: vi.fn(),
  previewReport: vi.fn(),
  fetchReportDataAvailability: vi.fn(),
  fetchReportingCatalog: vi.fn(),
}));

const savedLayoutsMock = vi.hoisted(() => ({
  deleteSavedLayout: vi.fn(),
  listSavedLayouts: vi.fn(),
  saveLayoutToApi: vi.fn(),
  updateSavedLayout: vi.fn(),
}));

const dashboardStoreMock = vi.hoisted(() => ({
  loadAll: vi.fn(),
}));

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ tenantId: 'tenant-1' }),
}));

vi.mock('../../state/useDashboardStore', () => ({
  default: (selector: (state: unknown) => unknown) =>
    selector({
      loadAll: dashboardStoreMock.loadAll,
      campaign: { data: null },
      parish: { data: null },
    }),
}));

vi.mock('../../lib/phase2Api', () => ({
  getReport: phase2ApiMock.getReport,
  previewReport: phase2ApiMock.previewReport,
  fetchReportDataAvailability: phase2ApiMock.fetchReportDataAvailability,
  fetchReportingCatalog: phase2ApiMock.fetchReportingCatalog,
}));

vi.mock('../../components/report-layout/savedReportLayouts', () => ({
  deleteSavedLayout: savedLayoutsMock.deleteSavedLayout,
  listSavedLayouts: savedLayoutsMock.listSavedLayouts,
  saveLayoutToApi: savedLayoutsMock.saveLayoutToApi,
  updateSavedLayout: savedLayoutsMock.updateSavedLayout,
}));

const reportPayload = {
  id: 'r1',
  name: 'SLB Monthly Social Report',
  description: 'May client report',
  filters: {
    template_key: 'slb_monthly_social_report',
    date_range: 'custom',
    start_date: '2026-05-01',
    end_date: '2026-05-31',
    client_id: 'slb-client',
    account_id: 'act_791712443035541',
    page_id: 'slb-page',
  },
  layout: { schema_version: 'report.v1' },
  is_active: true,
  schedule_enabled: false,
  schedule_cron: '',
  delivery_emails: [],
  last_scheduled_at: null,
  created_at: '2026-06-01T00:00:00Z',
  updated_at: '2026-06-01T00:00:00Z',
};

const availabilityPayload = {
  schema_version: 'report_data_availability.v1',
  stored_aggregate_only: true,
  no_live_provider_calls: true,
  template: {
    template_key: 'slb_monthly_social_report',
    label: 'SLB Monthly Social Report',
    version: 'v1',
    supported_datasets: ['organic_facebook_page'],
    required_sources: [],
    eligibility: {},
  },
  requested: {
    date_range: 'custom',
    start_date: '2026-05-01',
    end_date: '2026-05-31',
    client_id: 'slb-client',
    account_id: 'act_791712443035541',
    page_id: 'slb-page',
  },
  datasets: {
    organic_facebook_page: {
      dataset: 'organic_facebook_page',
      label: 'Facebook Page',
      row_count: 31,
      min_date: '2026-05-01',
      max_date: '2026-05-31',
      coverage_status: 'available',
      coverage_note: 'Stored Page metrics cover May 2026.',
      source_label: 'Meta Page Insights',
      metric_availability: {
        schema_version: 'report_metric_availability.v1',
        states: ['available', 'permission_gated'],
        summary: {
          available: 1,
          callable_no_data: 0,
          permission_gated: 1,
          unsupported: 0,
        },
        metrics: [
          {
            key: 'page_follows',
            catalog_dataset: 'organic_facebook_page',
            availability_state: 'available',
            availability_note: 'Stored Page follows rows exist.',
            row_count: 31,
            source_metric_keys: ['page_follows'],
            supported: true,
          },
          {
            key: 'page_reach',
            catalog_dataset: 'organic_facebook_page',
            availability_state: 'permission_gated',
            availability_note: 'Requires Meta read_insights approval.',
            row_count: 0,
            source_metric_keys: [],
            supported: false,
          },
        ],
      },
    },
  },
  blocking_datasets: [],
  warning_datasets: [],
  eligible_for_report_export: true,
  recommended_next_actions: [],
};

const previewPayload = {
  report: {
    id: 'r1',
    name: 'SLB Monthly Social Report',
    template_key: 'slb_monthly_social_report',
    schema_version: 'report.v1',
    catalog_schema_version: 'reporting_catalog.v1',
  },
  generated_at: '2026-06-16T10:00:00Z',
  date_range: { start_date: '2026-05-01', end_date: '2026-05-31' },
  pages: [
    {
      id: 'summary',
      title: 'Summary',
      sections: [
        {
          id: 'summary_widgets',
          type: 'widget_group',
          widgets: [
            {
              widget_id: 'organic_summary',
              dataset: 'organic_facebook_page',
              type: 'kpi',
              status: 'rendered',
              data: {
                title: 'Organic summary',
                metrics: [{ key: 'page_follows', label: 'Page follows', value: 6023 }],
              },
              coverage: null,
              warnings: [],
            },
          ],
        },
      ],
    },
  ],
  coverage_summary: { by_status: {}, datasets: [] },
  warnings: [],
  blocking_reasons: [],
  export_ready: true,
  preview_hash: 'hash-1',
};

const savedLayoutConfig = (title: string, text: string) => ({
  id: 'report-r1',
  title,
  cols: 12,
  rowHeight: 64,
  widgets: [
    {
      id: `${title.toLowerCase().replace(/\s+/g, '-')}-note`,
      type: 'note',
      title,
      x: 1,
      y: 1,
      w: 12,
      h: 2,
      options: { text },
    },
  ],
});

const savedLayoutRow = (overrides: Record<string, unknown> = {}) => ({
  id: 'layout-1',
  name: 'Boardroom layout',
  description: '',
  config: savedLayoutConfig('Boardroom layout', 'Boardroom saved layout'),
  is_shared: false,
  created_at: '2026-06-01T00:00:00Z',
  updated_at: '2026-06-01T00:00:00Z',
  ...overrides,
});

function renderBuilder() {
  return render(
    <MemoryRouter initialEntries={['/reports/r1/builder']}>
      <Routes>
        <Route path="/reports/:reportId/builder" element={<ReportLayoutPreview />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ReportLayoutPreview report builder route', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    phase2ApiMock.getReport.mockResolvedValue(reportPayload);
    phase2ApiMock.previewReport.mockResolvedValue(previewPayload);
    phase2ApiMock.fetchReportDataAvailability.mockResolvedValue(availabilityPayload);
    phase2ApiMock.fetchReportingCatalog.mockResolvedValue({
      schema_version: 'reporting_catalog.v1',
      dashboard_schema_version: 'dashboard.v1',
      report_schema_version: 'report.v1',
      metrics: [
        {
          key: 'page_follows',
          dataset: 'organic_facebook_page',
          widgets: ['kpi', 'line_chart'],
          dimensions: ['date'],
          is_future_gated: false,
          availability_state: 'available',
          availability_note: 'Metric is usable through the current stored reporting path.',
        },
        {
          key: 'page_reach',
          dataset: 'organic_facebook_page',
          widgets: ['kpi'],
          dimensions: ['date'],
          is_future_gated: false,
          availability_state: 'permission_gated',
          availability_note: 'Requires Meta read_insights approval.',
        },
      ],
      datasets: [],
      dimensions: [],
      widgets: [],
      coverage_policies: [],
      coverage_statuses: [],
      compatibility: {},
      validation: {},
    });
    savedLayoutsMock.listSavedLayouts.mockResolvedValue([]);
    savedLayoutsMock.deleteSavedLayout.mockResolvedValue(undefined);
    savedLayoutsMock.updateSavedLayout.mockResolvedValue(savedLayoutRow());
    savedLayoutsMock.saveLayoutToApi.mockResolvedValue({
      id: 'layout-1',
      name: 'SLB Monthly Social Report layout',
      description: '',
      config: {},
      is_shared: false,
      created_at: '2026-06-01T00:00:00Z',
      updated_at: '2026-06-01T00:00:00Z',
    });
  });

  it('seeds the canvas from the governed report preview and catalog', async () => {
    renderBuilder();

    expect(await screen.findByText('SLB Monthly Social Report layout')).toBeInTheDocument();
    expect(
      screen.getByText(/backend reporting catalog \(reporting_catalog\.v1\)/i),
    ).toBeInTheDocument();
    expect(screen.getByText('Page follows')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Back to rendered report' })).toHaveAttribute(
      'href',
      '/reports/r1',
    );
    expect(phase2ApiMock.getReport).toHaveBeenCalledWith('r1', expect.any(AbortSignal));
    expect(phase2ApiMock.previewReport).toHaveBeenCalledWith('r1', {}, expect.any(AbortSignal));
    expect(phase2ApiMock.fetchReportDataAvailability).toHaveBeenCalledWith(
      {
        template_key: 'slb_monthly_social_report',
        date_range: 'custom',
        start_date: '2026-05-01',
        end_date: '2026-05-31',
        client_id: 'slb-client',
        account_id: 'act_791712443035541',
        page_id: 'slb-page',
      },
      expect.any(AbortSignal),
    );
    expect(phase2ApiMock.fetchReportingCatalog).toHaveBeenCalledWith(expect.any(AbortSignal));
    expect(
      screen.getByText('Runtime metric availability loaded from stored report data.'),
    ).toBeInTheDocument();
    expect(dashboardStoreMock.loadAll).not.toHaveBeenCalled();
  });

  it('saves report-scoped generated layouts through the saved-layout API', async () => {
    const user = userEvent.setup();
    renderBuilder();

    await screen.findByText('SLB Monthly Social Report layout');
    await user.click(screen.getByRole('button', { name: 'Edit layout' }));
    await user.click(screen.getByRole('button', { name: 'Save layout' }));

    await waitFor(() =>
      expect(savedLayoutsMock.saveLayoutToApi).toHaveBeenCalledWith(
        expect.objectContaining({ id: 'report-r1', title: 'SLB Monthly Social Report layout' }),
        expect.objectContaining({ name: 'SLB Monthly Social Report layout' }),
      ),
    );
  });

  it('lists and switches report-scoped saved layouts', async () => {
    const user = userEvent.setup();
    savedLayoutsMock.listSavedLayouts.mockResolvedValue([
      savedLayoutRow(),
      savedLayoutRow({
        id: 'layout-2',
        name: 'Compact layout',
        config: savedLayoutConfig('Compact layout', 'Compact saved layout'),
      }),
      savedLayoutRow({
        id: 'layout-other',
        name: 'Other dashboard layout',
        config: { ...savedLayoutConfig('Other dashboard layout', 'Other layout'), id: 'other' },
      }),
    ]);

    renderBuilder();

    const selector = await screen.findByLabelText('Saved layout');
    expect(selector).toHaveValue('layout-1');
    expect(screen.getByText('Boardroom saved layout')).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Boardroom layout' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Compact layout' })).toBeInTheDocument();
    expect(
      screen.queryByRole('option', { name: 'Other dashboard layout' }),
    ).not.toBeInTheDocument();

    await user.selectOptions(selector, 'layout-2');

    expect(await screen.findByText('Compact saved layout')).toBeInTheDocument();
    expect(screen.getByText('Loaded Compact layout')).toBeInTheDocument();
  });

  it('restores missing governed report widgets from the preview source', async () => {
    const user = userEvent.setup();
    savedLayoutsMock.listSavedLayouts.mockResolvedValue([savedLayoutRow()]);

    renderBuilder();

    await screen.findByText('Boardroom saved layout');
    await user.click(screen.getByRole('button', { name: 'Edit layout' }));
    expect(screen.getByLabelText('Add Note widget')).toBeInTheDocument();
    expect(screen.queryByLabelText('Add KPI widget')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Add Bar widget')).not.toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Page follows (available)' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Page Reach (gated)' })).toBeDisabled();

    await user.selectOptions(
      screen.getByLabelText('Governed report widget'),
      'organic_summary-page_follows',
    );
    await user.click(screen.getByRole('button', { name: 'Add governed widget' }));

    expect(screen.getByRole('button', { name: 'Configure Page follows' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Save layout' }));
    await waitFor(() =>
      expect(savedLayoutsMock.saveLayoutToApi).toHaveBeenCalledWith(
        expect.objectContaining({
          widgets: expect.arrayContaining([
            expect.objectContaining({
              id: 'organic_summary-page_follows',
              title: 'Page follows',
              data: 6023,
            }),
          ]),
        }),
        expect.objectContaining({ id: 'layout-1' }),
      ),
    );
  });

  it('toggles tenant sharing for the selected saved layout', async () => {
    const user = userEvent.setup();
    savedLayoutsMock.listSavedLayouts.mockResolvedValue([savedLayoutRow()]);
    savedLayoutsMock.updateSavedLayout.mockResolvedValue(savedLayoutRow({ is_shared: true }));

    renderBuilder();

    await screen.findByText('Boardroom saved layout');
    const shareToggle = screen.getByRole('checkbox', { name: 'Share with tenant' });
    expect(shareToggle).not.toBeChecked();

    await user.click(shareToggle);

    await waitFor(() =>
      expect(savedLayoutsMock.updateSavedLayout).toHaveBeenCalledWith('layout-1', {
        is_shared: true,
      }),
    );
    expect(screen.getByText('Shared with tenant')).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: 'Share with tenant' })).toBeChecked();
    expect(screen.getByRole('option', { name: 'Boardroom layout (shared)' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Edit layout' }));
    await user.click(screen.getByRole('button', { name: 'Save layout' }));

    await waitFor(() =>
      expect(savedLayoutsMock.saveLayoutToApi).toHaveBeenCalledWith(
        expect.objectContaining({ id: 'report-r1', title: 'Boardroom layout' }),
        expect.objectContaining({
          id: 'layout-1',
          name: 'Boardroom layout',
          is_shared: true,
        }),
      ),
    );
  });

  it('renames and deletes the selected saved layout row', async () => {
    const user = userEvent.setup();
    const promptSpy = vi.spyOn(window, 'prompt').mockReturnValue('Executive layout');
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    savedLayoutsMock.listSavedLayouts.mockResolvedValue([savedLayoutRow()]);
    savedLayoutsMock.updateSavedLayout.mockResolvedValue(
      savedLayoutRow({ name: 'Executive layout' }),
    );

    renderBuilder();

    await screen.findByText('Boardroom saved layout');
    await user.click(screen.getByRole('button', { name: 'Rename' }));

    await waitFor(() =>
      expect(savedLayoutsMock.updateSavedLayout).toHaveBeenCalledWith('layout-1', {
        name: 'Executive layout',
      }),
    );
    expect(screen.getByRole('option', { name: 'Executive layout' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Delete' }));

    await waitFor(() =>
      expect(savedLayoutsMock.deleteSavedLayout).toHaveBeenCalledWith('layout-1'),
    );
    expect(screen.getByLabelText('Saved layout')).toHaveValue('browser');
    expect(screen.queryByRole('option', { name: 'Executive layout' })).not.toBeInTheDocument();
    expect(screen.getByText('Saved layout deleted')).toBeInTheDocument();

    promptSpy.mockRestore();
    confirmSpy.mockRestore();
  });
});
