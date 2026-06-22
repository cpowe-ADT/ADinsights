import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  delete: vi.fn(),
}));

vi.mock('./apiClient', () => ({
  __esModule: true,
  default: apiClientMock,
  appendQueryParams: (path: string, params?: Record<string, unknown>) => {
    if (!params) return path;
    const qs = Object.entries(params)
      .filter(([, v]) => v !== undefined)
      .map(([k, v]) => `${k}=${v}`)
      .join('&');
    return qs ? `${path}?${qs}` : path;
  },
}));

import {
  createReport,
  createSlbMonthlyReportTemplate,
  fetchDashboardLibrary,
  fetchReportingCatalog,
  fetchHealthOverview,
  fetchSyncHealth,
  getAlert,
  getDashboardDefinition,
  getReport,
  listAlerts,
  listReports,
  listSummaries,
  previewDashboardWidget,
} from './phase2Api';

describe('phase2Api', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('fetchDashboardLibrary', () => {
    it('normalizes response with systemTemplates and savedDashboards', async () => {
      apiClientMock.get.mockResolvedValue({
        generatedAt: '2026-04-10',
        systemTemplates: [
          {
            id: 't1',
            name: 'Template',
            template_key: 'meta_campaign_performance',
            type: 'System',
            owner: 'System',
            tags: [],
            description: '',
            route: '/a',
          },
        ],
        savedDashboards: [],
      });

      const result = await fetchDashboardLibrary();
      expect(result.systemTemplates).toHaveLength(1);
      expect(result.systemTemplates[0].name).toBe('Template');
    });
  });

  describe('fetchReportingCatalog', () => {
    it('fetches the governed reporting catalog payload', async () => {
      apiClientMock.get.mockResolvedValue({
        schema_version: 'reporting_catalog.v1',
        dashboard_schema_version: 'dashboard.v1',
        datasets: [
          { key: 'paid_meta_ads', status: 'active_v1', is_future_gated: false },
          { key: 'combined_social', status: 'future_gated', is_future_gated: true },
        ],
        metrics: [
          {
            key: 'spend',
            dataset: 'paid_meta_ads',
            widgets: ['kpi', 'line_chart', 'data_table'],
            dimensions: ['date', 'campaign'],
            is_future_gated: false,
          },
        ],
        dimensions: [
          { key: 'date', datasets: ['paid_meta_ads'] },
          { key: 'campaign', datasets: ['paid_meta_ads'] },
        ],
        widgets: [
          { key: 'kpi', status: 'active_v1', is_future_gated: false },
          { key: 'scatter_chart', status: 'future_gated', is_future_gated: true },
        ],
        coverage_policies: ['render_with_warning', 'require_full_coverage'],
        coverage_statuses: ['fresh', 'stale', 'source_disconnected'],
        compatibility: {
          time_dimensions: ['date', 'week', 'month'],
          geography_dimensions: ['region', 'parish'],
          source_label_datasets: ['combined_paid_media', 'combined_social'],
          future_gated_datasets: ['combined_social'],
          future_gated_widgets: ['scatter_chart'],
          relative_date_ranges: ['last_30d', 'last_90d'],
          table: { requires_row_limit: true, max_row_limit: 500 },
          line_chart: { requires_one_of_dimensions: ['date', 'week', 'month'] },
          map: { requires_one_of_dimensions: ['region', 'parish'] },
        },
        validation: {
          legacy_layouts_without_schema_version: 'accepted',
          dashboard_v1_layouts: 'validated',
          deprecated_or_unknown_page_metrics: ['page_video_views_10s'],
        },
      });

      const catalog = await fetchReportingCatalog();

      expect(apiClientMock.get).toHaveBeenCalledWith('/dashboards/reporting-catalog/', {
        signal: undefined,
      });
      expect(catalog.dashboard_schema_version).toBe('dashboard.v1');
      expect(catalog.datasets.find((dataset) => dataset.key === 'combined_social')).toMatchObject({
        is_future_gated: true,
      });
      expect(catalog.metrics[0]).toMatchObject({
        key: 'spend',
        dataset: 'paid_meta_ads',
      });
      expect(catalog.compatibility.table).toEqual({
        requires_row_limit: true,
        max_row_limit: 500,
      });
      expect(catalog.validation.deprecated_or_unknown_page_metrics).toContain(
        'page_video_views_10s',
      );
    });
  });

  describe('previewDashboardWidget', () => {
    it('posts a governed dashboard.v1 widget preview payload', async () => {
      apiClientMock.post.mockResolvedValue({
        widget_id: 'paid_spend_kpi',
        dataset: 'paid_meta_ads',
        type: 'kpi',
        data: { kind: 'kpi', metrics: [] },
        coverage: {
          coverage_status: 'fresh',
          coverage_note: 'Warehouse aggregate metrics covers the requested range.',
        },
        warnings: [],
      });

      const widget = {
        id: 'paid_spend_kpi',
        type: 'kpi',
        dataset: 'paid_meta_ads',
        metrics: ['spend'],
        dimensions: [],
        filters: { date_range: 'last_30d' },
        coverage_policy: 'render_with_warning',
        visual: { source_labels: true },
      };
      const result = await previewDashboardWidget({ widget, account_id: 'act_1' });

      expect(apiClientMock.post).toHaveBeenCalledWith(
        '/dashboards/widget-preview/',
        { widget, account_id: 'act_1' },
        { signal: undefined },
      );
      expect(result.coverage.coverage_status).toBe('fresh');
    });
  });

  describe('getDashboardDefinition', () => {
    it('fetches by id', async () => {
      apiClientMock.get.mockResolvedValue({ id: 'd1', name: 'Test' });
      const result = await getDashboardDefinition('d1');
      expect(result.id).toBe('d1');
    });
  });

  describe('listReports', () => {
    it('handles array response', async () => {
      apiClientMock.get.mockResolvedValue([]);
      const result = await listReports();
      expect(result).toEqual([]);
    });
  });

  describe('createReport', () => {
    it('posts report data', async () => {
      apiClientMock.post.mockResolvedValue({ id: 'r1', name: 'New Report' });
      const result = await createReport({ name: 'New Report', description: '' });
      expect(apiClientMock.post).toHaveBeenCalled();
      expect(result.name).toBe('New Report');
    });
  });

  describe('createSlbMonthlyReportTemplate', () => {
    it('posts the SLB template creation request', async () => {
      apiClientMock.post.mockResolvedValue({
        id: 'r-slb',
        name: 'SLB report',
        layout: { schema_version: 'report.v1', template_key: 'slb_monthly_social_report' },
      });

      const result = await createSlbMonthlyReportTemplate({
        name: 'SLB report',
        date_range: 'last_month',
      });

      expect(apiClientMock.post).toHaveBeenCalledWith('/reports/slb-monthly-template/', {
        name: 'SLB report',
        date_range: 'last_month',
      });
      expect(result.layout.template_key).toBe('slb_monthly_social_report');
    });
  });

  describe('getReport', () => {
    it('fetches by id', async () => {
      apiClientMock.get.mockResolvedValue({ id: 'r1', name: 'Report' });
      const result = await getReport('r1');
      expect(result.id).toBe('r1');
    });
  });

  describe('listAlerts', () => {
    it('handles array response', async () => {
      apiClientMock.get.mockResolvedValue([{ id: 'a1' }]);
      const result = await listAlerts();
      expect(result).toHaveLength(1);
    });
  });

  describe('getAlert', () => {
    it('fetches by id', async () => {
      apiClientMock.get.mockResolvedValue({ id: 'a1', name: 'Alert' });
      const result = await getAlert('a1');
      expect(result.id).toBe('a1');
    });
  });

  describe('listSummaries', () => {
    it('handles array response', async () => {
      apiClientMock.get.mockResolvedValue([]);
      const result = await listSummaries();
      expect(result).toEqual([]);
    });
  });

  describe('fetchSyncHealth', () => {
    it('returns sync health data', async () => {
      const mockData = {
        generated_at: '2026-04-10',
        stale_after_minutes: 60,
        counts: { total: 0, fresh: 0, stale: 0, failed: 0, missing: 0, inactive: 0 },
        rows: [],
      };
      apiClientMock.get.mockResolvedValue(mockData);
      const result = await fetchSyncHealth();
      expect(result.rows).toEqual([]);
    });
  });

  describe('fetchHealthOverview', () => {
    it('returns health overview data', async () => {
      const mockData = { generated_at: '2026-04-10', overall_status: 'ok', cards: [] };
      apiClientMock.get.mockResolvedValue(mockData);
      const result = await fetchHealthOverview();
      expect(result.overall_status).toBe('ok');
    });
  });
});
