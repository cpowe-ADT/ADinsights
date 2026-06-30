import { describe, expect, it } from 'vitest';

import type {
  ReportDataAvailabilityResponse,
  ReportPreviewResponse,
  ReportingCatalogResponse,
} from '../../../lib/phase2Api';
import {
  mergeGovernedWidgets,
  reportLayoutId,
  reportPreviewToLayout,
  reportingCatalogToWidgets,
} from '../reportPreviewAdapter';

const basePreview: ReportPreviewResponse = {
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
                metrics: [
                  { key: 'page_follows', label: 'Page follows', value: 6023 },
                  { key: 'post_comments', label: 'Post comments', value: null },
                ],
              },
              coverage: null,
              warnings: [],
            },
            {
              widget_id: 'organic_trend',
              dataset: 'organic_facebook_posts',
              type: 'line_chart',
              metrics: ['post_reactions', 'post_shares'],
              dimensions: ['date'],
              status: 'rendered',
              data: {
                title: 'Organic engagement trend',
                x: 'date',
                rows: [
                  { date: '2026-05-01', post_reactions: 2, post_shares: null },
                  { date: '2026-05-02', post_reactions: 3, post_shares: 1 },
                ],
              },
              coverage: null,
              warnings: [],
            },
            {
              widget_id: 'top_posts_table',
              dataset: 'organic_facebook_page',
              type: 'data_table',
              metrics: ['post_reactions', 'post_comments', 'post_shares'],
              dimensions: ['post'],
              status: 'rendered',
              data: {
                title: 'Top posts',
                columns: ['post', 'content', 'post_reactions', 'post_comments', 'post_shares'],
                rows: [
                  {
                    post: 'page-123_1',
                    content: 'Application deadline reminder',
                    post_reactions: 16,
                    post_comments: 0,
                    post_shares: 8,
                  },
                ],
              },
              coverage: null,
              warnings: [],
            },
            {
              widget_id: 'reach_blocked',
              dataset: 'organic_facebook_page',
              type: 'kpi',
              status: 'blocked',
              data: {},
              coverage: null,
              warnings: ['Organic reach requires Meta read_insights approval.'],
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

describe('reportPreviewToLayout', () => {
  it('uses a stable report-scoped layout id', () => {
    expect(reportLayoutId('r1')).toBe('report-r1');
    expect(reportPreviewToLayout(basePreview).id).toBe('report-r1');
  });

  it('expands governed KPI metrics without turning null into zero', () => {
    const layout = reportPreviewToLayout(basePreview);
    const follows = layout.widgets.find((widget) => widget.id === 'organic_summary-page_follows');
    const comments = layout.widgets.find((widget) => widget.id === 'organic_summary-post_comments');

    expect(follows).toMatchObject({ type: 'kpi', title: 'Page follows', data: 6023 });
    expect(comments).toMatchObject({ type: 'kpi', title: 'Post comments', data: null });
    expect(follows?.source).toEqual({
      dataset: 'organic_facebook_page',
      widgetId: 'organic_summary',
      metrics: ['page_follows'],
    });
    expect(comments?.source).toEqual({
      dataset: 'organic_facebook_page',
      widgetId: 'organic_summary',
      metrics: ['post_comments'],
    });
  });

  it('maps governed trend widgets to line widgets with nullable series values', () => {
    const layout = reportPreviewToLayout(basePreview);
    const trend = layout.widgets.find((widget) => widget.id === 'organic_trend');

    expect(trend).toMatchObject({
      type: 'line',
      title: 'Organic engagement trend',
      options: {
        series: [
          { key: 'post_reactions', label: 'Post Reactions' },
          { key: 'post_shares', label: 'Post Shares' },
        ],
      },
    });
    expect(trend?.data).toEqual([
      { date: '2026-05-01', post_reactions: 2, post_shares: null },
      { date: '2026-05-02', post_reactions: 3, post_shares: 1 },
    ]);
    expect(trend?.source).toEqual({
      dataset: 'organic_facebook_posts',
      widgetId: 'organic_trend',
      metrics: ['post_reactions', 'post_shares'],
    });
  });

  it('binds governed table widgets to declared metrics instead of row dimensions', () => {
    const layout = reportPreviewToLayout(basePreview);
    const table = layout.widgets.find((widget) => widget.id === 'top_posts_table');

    expect(table).toMatchObject({
      type: 'table',
      title: 'Top posts',
      source: {
        dataset: 'organic_facebook_page',
        widgetId: 'top_posts_table',
        metrics: ['post_reactions', 'post_comments', 'post_shares'],
      },
    });
    expect(table?.source?.metrics).not.toContain('post');
    expect(table?.source?.metrics).not.toContain('content');
  });

  it('keeps blocked governed widgets as notes instead of placeholder values', () => {
    const layout = reportPreviewToLayout(basePreview);
    const note = layout.widgets.find((widget) => widget.id === 'reach_blocked-note');

    expect(note).toMatchObject({
      type: 'note',
      title: 'reach blocked',
      options: { text: 'Organic reach requires Meta read_insights approval.' },
    });
  });

  it('builds scoped catalog-governed widgets with runtime availability states', () => {
    const catalog: ReportingCatalogResponse = {
      schema_version: 'reporting_catalog.v1',
      dashboard_schema_version: 'dashboard.v1',
      report_schema_version: 'report.v1',
      datasets: [],
      metrics: [
        {
          key: 'page_follows',
          dataset: 'organic_facebook_page',
          widgets: ['kpi', 'line_chart'],
          dimensions: ['date'],
          is_future_gated: false,
          availability_state: 'available',
          availability_note: 'Catalog says available.',
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
        {
          key: 'sessions',
          dataset: 'ga4_web',
          widgets: ['kpi'],
          dimensions: ['date'],
          is_future_gated: true,
          availability_state: 'unsupported',
          availability_note: 'Future gated.',
        },
      ],
      dimensions: [],
      widgets: [],
      coverage_policies: [],
      coverage_statuses: [],
      compatibility: {
        time_dimensions: [],
        geography_dimensions: [],
        source_label_datasets: [],
        future_gated_datasets: [],
        future_gated_widgets: [],
        relative_date_ranges: [],
        table: { requires_row_limit: true, max_row_limit: 500 },
        line_chart: { requires_one_of_dimensions: [] },
        map: { requires_one_of_dimensions: [] },
      },
      validation: {
        legacy_layouts_without_schema_version: 'accepted',
        dashboard_v1_layouts: 'validated',
        deprecated_or_unknown_page_metrics: [],
      },
    };
    const availability: ReportDataAvailabilityResponse = {
      schema_version: 'report_data_availability.v1',
      stored_aggregate_only: true,
      no_live_provider_calls: true,
      template: {
        template_key: 'slb_monthly_social_report',
        label: 'SLB',
        version: 'v1',
        supported_datasets: ['organic_facebook_page'],
        required_sources: [],
        eligibility: {},
      },
      requested: {
        date_range: 'custom',
        start_date: '2026-05-01',
        end_date: '2026-05-31',
        client_id: '',
        account_id: '',
        page_id: 'slb-page',
      },
      datasets: {
        organic_facebook_page: {
          dataset: 'organic_facebook_page',
          label: 'Facebook Page',
          row_count: 31,
          min_date: '2026-05-01',
          max_date: '2026-05-31',
          coverage_status: 'fresh',
          coverage_note: 'Stored rows cover the requested report range.',
          source_label: 'Meta Page',
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
                availability_note: 'Runtime rows exist.',
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

    const widgets = reportingCatalogToWidgets(catalog, availability);

    expect(widgets.map((widget) => widget.id)).toEqual([
      'catalog-organic_facebook_page-page_follows-kpi',
      'catalog-organic_facebook_page-page_reach-kpi',
    ]);
    expect(widgets[0]).toMatchObject({
      title: 'Page Follows',
      data: null,
      source: {
        dataset: 'organic_facebook_page',
        metrics: ['page_follows'],
        availability: [{ key: 'page_follows', state: 'available', rowCount: 31 }],
      },
    });
    expect(widgets[1].source?.availability?.[0]).toMatchObject({
      key: 'page_reach',
      state: 'permission_gated',
      note: 'Requires Meta read_insights approval.',
      rowCount: 0,
    });
  });

  it('prefers preview widgets when catalog widgets have the same source signature', () => {
    const previewLayout = reportPreviewToLayout(basePreview);
    const catalogDuplicate = {
      id: 'catalog-organic_facebook_page-page_follows-kpi',
      type: 'kpi' as const,
      title: 'Page Follows',
      x: 1,
      y: 1,
      w: 3,
      h: 2,
      data: null,
      source: {
        dataset: 'organic_facebook_page',
        widgetId: 'catalog:organic_facebook_page:page_follows',
        metrics: ['page_follows'],
      },
    };

    const merged = mergeGovernedWidgets(previewLayout.widgets, [catalogDuplicate]);

    expect(
      merged.filter((widget) => widget.source?.metrics?.includes('page_follows')),
    ).toHaveLength(1);
    expect(merged.find((widget) => widget.source?.metrics?.includes('page_follows'))?.id).toBe(
      'organic_summary-page_follows',
    );
  });
});
