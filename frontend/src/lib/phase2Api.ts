import apiClient, { appendQueryParams } from './apiClient';

export type DashboardTemplateKey =
  | 'meta_executive_overview'
  | 'meta_campaign_performance'
  | 'meta_creative_insights'
  | 'meta_budget_pacing'
  | 'meta_parish_map'
  | 'meta_page_insights';

export type DashboardMetricKey =
  | 'spend'
  | 'impressions'
  | 'reach'
  | 'clicks'
  | 'conversions'
  | 'roas'
  | 'ctr'
  | 'cpc'
  | 'cpm'
  | 'cpa'
  | 'frequency';

export type DashboardLibraryItem = {
  id: string;
  kind: 'system_template' | 'saved_dashboard';
  templateKey: DashboardTemplateKey;
  name: string;
  type: string;
  owner: string;
  updatedAt: string;
  tags: string[];
  description: string;
  route: string;
  defaultMetric?: DashboardMetricKey;
  isActive?: boolean;
};

export type DashboardLibraryResponse = {
  generatedAt: string;
  systemTemplates: DashboardLibraryItem[];
  savedDashboards: DashboardLibraryItem[];
};

export type DashboardDefinition = {
  id: string;
  name: string;
  description: string;
  template_key: DashboardTemplateKey;
  filters: Record<string, unknown>;
  layout: Record<string, unknown>;
  default_metric: DashboardMetricKey;
  is_active: boolean;
  owner_email?: string | null;
  created_at: string;
  updated_at: string;
};

export type ReportDefinition = {
  id: string;
  name: string;
  description: string;
  filters: Record<string, unknown>;
  layout: Record<string, unknown>;
  is_active: boolean;
  schedule_enabled: boolean;
  schedule_cron: string;
  delivery_emails: string[];
  last_scheduled_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ReportExportJob = {
  id: string;
  report_id: string;
  export_format: 'csv' | 'pdf' | 'png';
  status: 'queued' | 'running' | 'completed' | 'failed';
  artifact_path: string;
  error_message: string;
  metadata: Record<string, unknown>;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type AlertRule = {
  id: string;
  name: string;
  metric: string;
  comparison_operator: string;
  threshold: string;
  lookback_hours: number;
  severity: string;
  is_active: boolean;
  paused_until?: string | null;
  notification_channels?: string[];
  created_at: string;
  updated_at: string;
};

export type AISummary = {
  id: string;
  title: string;
  summary: string;
  payload: Record<string, unknown>;
  source: string;
  model_name: string;
  status: 'generated' | 'fallback' | 'failed';
  generated_at: string;
  created_at: string;
  updated_at: string;
};

export type SyncHealthRow = {
  id: string;
  name: string;
  provider: string | null;
  schedule_type: string;
  is_active: boolean;
  state: 'fresh' | 'stale' | 'failed' | 'missing' | 'inactive';
  last_synced_at: string | null;
  last_job_status: string | null;
  last_job_error: string | null;
};

export type SyncHealthResponse = {
  generated_at: string;
  stale_after_minutes: number;
  counts: {
    total: number;
    fresh: number;
    stale: number;
    failed: number;
    missing: number;
    inactive: number;
  };
  rows: SyncHealthRow[];
};

export type HealthOverviewCard = {
  key: 'api' | 'airbyte' | 'dbt' | 'timezone';
  http_status: number;
  status: string;
  detail?: string | null;
  payload: Record<string, unknown>;
};

export type HealthOverviewResponse = {
  generated_at: string;
  overall_status: 'ok' | 'degraded' | 'error';
  cards: HealthOverviewCard[];
};

export type ReportingCatalogDataset = {
  key: string;
  status: string;
  is_future_gated: boolean;
};

export type ReportingCatalogMetric = {
  key: string;
  dataset: string;
  widgets: string[];
  dimensions: string[];
  is_future_gated: boolean;
  availability_state?: 'available' | 'callable_no_data' | 'permission_gated' | 'unsupported';
  availability_note?: string;
};

export type ReportingCatalogDimension = {
  key: string;
  datasets: string[];
};

export type ReportingCatalogWidget = {
  key: string;
  status: string;
  is_future_gated: boolean;
};

export type ReportingCatalogCompatibility = {
  time_dimensions: string[];
  geography_dimensions: string[];
  source_label_datasets: string[];
  future_gated_datasets: string[];
  future_gated_widgets: string[];
  metric_availability_states?: string[];
  relative_date_ranges: string[];
  table: {
    requires_row_limit: boolean;
    max_row_limit: number;
  };
  line_chart: {
    requires_one_of_dimensions: string[];
  };
  map: {
    requires_one_of_dimensions: string[];
  };
};

export type ReportingCatalogValidation = {
  legacy_layouts_without_schema_version: string;
  dashboard_v1_layouts: string;
  deprecated_or_unknown_page_metrics: string[];
};

export type ReportingCatalogResponse = {
  schema_version: 'reporting_catalog.v1';
  dashboard_schema_version: 'dashboard.v1';
  report_schema_version?: 'report.v1';
  datasets: ReportingCatalogDataset[];
  metrics: ReportingCatalogMetric[];
  dimensions: ReportingCatalogDimension[];
  widgets: ReportingCatalogWidget[];
  coverage_policies: string[];
  coverage_statuses: string[];
  source_metric_semantics?: Record<string, Record<string, unknown>>;
  compatibility: ReportingCatalogCompatibility;
  validation: ReportingCatalogValidation;
};

export type ReportTemplateDefinition = {
  template_key: string;
  label: string;
  version: string;
  supported_datasets: string[];
  required_sources: string[];
  eligibility: Record<string, unknown>;
};

export type ReportTemplateRegistryResponse = {
  schema_version: 'report_template_registry.v1';
  templates: ReportTemplateDefinition[];
};

export type ReportMetricAvailabilityState =
  | 'available'
  | 'callable_no_data'
  | 'permission_gated'
  | 'unsupported';

export type ReportMetricAvailabilityEntry = {
  key: string;
  catalog_dataset: string;
  availability_state: ReportMetricAvailabilityState;
  availability_note: string;
  row_count: number;
  source_metric_keys: string[];
  supported: boolean;
};

export type ReportMetricAvailability = {
  schema_version: 'report_metric_availability.v1';
  states: ReportMetricAvailabilityState[];
  summary: Record<ReportMetricAvailabilityState, number>;
  metrics: ReportMetricAvailabilityEntry[];
};

export type ReportDataAvailabilityDataset = {
  dataset: string;
  label: string;
  row_count: number;
  min_date: string | null;
  max_date: string | null;
  coverage_status: string;
  coverage_note: string;
  source_label: string;
  metric_availability?: ReportMetricAvailability;
  scope_diagnostic?: {
    code: string;
    message: string;
    required_action: string;
    available_account_count?: number;
    client_id?: string;
    linked_meta_ad_account_ids?: string[];
    requested_account?: {
      id?: string;
      account_id: string;
      external_id?: string;
      name?: string;
      currency?: string;
    };
    credential_status?: {
      status: string;
      provider: string;
      matched_account_id: string | null;
      token_status: string | null;
      last_validated_at: string | null;
    };
  };
  available_accounts?: Array<{
    id: string;
    account_id: string;
    external_id: string;
    name: string;
    currency: string;
    row_count: number;
    min_date: string | null;
    max_date: string | null;
  }>;
  available_pages?: Array<{
    page_id: string;
    name: string;
    can_analyze: boolean;
    is_default: boolean;
    last_synced_at: string | null;
    last_posts_synced_at: string | null;
    page_insight_row_count: number;
    post_count: number;
    post_insight_row_count: number;
    min_date: string | null;
    max_date: string | null;
  }>;
  post_count?: number;
  published_post_count?: number;
};

export type ReportDataAvailabilityResponse = {
  schema_version: 'report_data_availability.v1';
  stored_aggregate_only: boolean;
  no_live_provider_calls: boolean;
  template: ReportTemplateDefinition;
  requested: {
    date_range: string;
    start_date: string;
    end_date: string;
    client_id: string;
    account_id: string;
    page_id: string;
  };
  datasets: Record<string, ReportDataAvailabilityDataset>;
  blocking_datasets: string[];
  warning_datasets: string[];
  eligible_for_report_export: boolean;
  recommended_next_actions: string[];
};

export type DashboardV1Widget = {
  id: string;
  type: string;
  dataset: string;
  metrics: string[];
  dimensions: string[];
  filters: Record<string, unknown>;
  coverage_policy: string;
  visual?: Record<string, unknown>;
};

export type DashboardWidgetCoverage = {
  dataset: string;
  requested_start_date: string;
  requested_end_date: string;
  covered_start_date: string | null;
  covered_end_date: string | null;
  coverage_status: string;
  history_status: string;
  freshness_status: string;
  last_successful_sync_at: string | null;
  row_count: number;
  source_label: string;
  coverage_note: string;
};

export type DashboardWidgetPreviewResponse = {
  widget_id: string;
  dataset: string;
  type: string;
  status?: 'rendered' | 'blocked' | 'error';
  metrics?: string[];
  dimensions?: string[];
  data: Record<string, unknown>;
  coverage: DashboardWidgetCoverage | null;
  warnings: string[];
  error?: string;
};

export type ReportPreviewSection = {
  id: string;
  type: string;
  widgets: DashboardWidgetPreviewResponse[];
};

export type ReportPreviewPage = {
  id: string;
  title: string;
  sections: ReportPreviewSection[];
};

export type ReportCoverageDatasetSummary = {
  dataset: string;
  statuses: Record<string, number>;
  row_count: number;
  covered_start_date: string | null;
  covered_end_date: string | null;
  source_label?: string | null;
  notes: string[];
};

export type ReportPreviewResponse = {
  report: {
    id: string;
    name: string;
    template_key: string;
    schema_version: 'report.v1';
    catalog_schema_version: string;
  };
  generated_at: string;
  date_range: Record<string, unknown>;
  pages: ReportPreviewPage[];
  coverage_summary: {
    by_status: Record<string, number>;
    datasets: ReportCoverageDatasetSummary[];
  };
  warnings: string[];
  blocking_reasons: string[];
  export_ready: boolean;
  preview_hash: string;
};

export type ReportSourceHealth = {
  schema_version: string;
  stored_aggregate_only: boolean;
  no_live_provider_calls: boolean;
  meta_credentials: {
    credential_count: number;
    token_status_counts: Record<string, number>;
    has_valid_credential: boolean;
    has_reauth_required: boolean;
    required_scope_coverage: {
      present: string[];
      missing: string[];
    };
    latest_validated_at: string | null;
    latest_expires_at: string | null;
  };
  meta_page_connection: {
    connection_count: number;
    active_count: number;
    inactive_count: number;
    has_active_connection: boolean;
    has_usable_page_auth?: boolean;
    usable_page_auth_count?: number;
    unusable_page_auth_count?: number;
    page_auth_status_counts?: Record<string, number>;
    required_scope_coverage: {
      present: string[];
      missing: string[];
    };
    latest_token_expires_at: string | null;
  };
  meta_airbyte: {
    connection_count: number;
    active_count: number;
    inactive_count: number;
    last_job_status_counts: Record<string, number>;
    latest_synced_at: string | null;
    latest_completed_at: string | null;
    sanitized_error_categories: Record<string, number>;
  };
  stored_assets: Record<string, number>;
  stored_rows: Record<string, unknown>;
  recommended_next_actions: string[];
  remediation_actions?: Array<{
    dataset: string;
    code: string;
    label: string;
    command_template: string;
    dry_run_command_template?: string;
    no_live_provider_calls?: boolean;
    no_render_export_provider_calls?: boolean;
    live_provider_calls_during_backfill?: boolean;
    aggregate_only?: boolean;
    notes?: string[];
    prerequisites?: string[];
  }>;
};

export type ReportDiagnosticsResponse = {
  report: {
    id: string;
    name: string;
    schema_version: string;
    template_key: string;
  };
  generated_at: string;
  date_range: Record<string, unknown>;
  datasets: Array<{
    dataset: string;
    coverage_status: string;
    freshness_status: string;
    retained_range: { start_date: string | null; end_date: string | null };
    row_count: number;
    source_label: string;
    last_successful_sync_at: string | null;
    notes: string[];
    recommended_next_action: string;
  }>;
  coverage_summary: ReportPreviewResponse['coverage_summary'] | Record<string, unknown>;
  blocking_reasons: string[];
  export_ready: boolean;
  preview_hash: string;
  preview_error: { status: string; errors: string[] } | null;
  source_health?: ReportSourceHealth;
  export_history: Array<{
    id: string;
    format: string;
    status: string;
    created_at: string;
    completed_at: string | null;
    preview_hash: string;
    delivery_status: string;
    blocking_reasons: string[];
  }>;
};

export type AuditLogEntry = {
  id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  metadata: Record<string, unknown>;
  created_at: string;
  user: { id?: string; email?: string } | null;
};

export type PaginatedResponse<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

function normalizeDashboardLibraryItem(
  item: Record<string, unknown>,
  fallbackKind: DashboardLibraryItem['kind'],
): DashboardLibraryItem {
  return {
    id: String(item.id ?? ''),
    kind:
      item.kind === 'saved_dashboard' || item.kind === 'system_template' ? item.kind : fallbackKind,
    templateKey: String(
      item.template_key ?? item.templateKey ?? 'meta_campaign_performance',
    ) as DashboardTemplateKey,
    name: String(item.name ?? ''),
    type: String(item.type ?? 'Saved dashboard'),
    owner: String(item.owner ?? 'Team'),
    updatedAt: String(item.updatedAt ?? item.updated_at ?? ''),
    tags: Array.isArray(item.tags) ? item.tags.map((tag) => String(tag)) : [],
    description: String(item.description ?? ''),
    route: String(item.route ?? ''),
    defaultMetric: item.defaultMetric
      ? (String(item.defaultMetric) as DashboardMetricKey)
      : item.default_metric
        ? (String(item.default_metric) as DashboardMetricKey)
        : undefined,
    isActive:
      typeof item.isActive === 'boolean'
        ? item.isActive
        : typeof item.is_active === 'boolean'
          ? item.is_active
          : undefined,
  };
}

function normalizeDashboardLibraryResponse(
  payload: Record<string, unknown>,
): DashboardLibraryResponse {
  const systemTemplates = Array.isArray(payload.systemTemplates)
    ? payload.systemTemplates.map((item) =>
        normalizeDashboardLibraryItem(item as Record<string, unknown>, 'system_template'),
      )
    : [];
  const savedDashboards = Array.isArray(payload.savedDashboards)
    ? payload.savedDashboards.map((item) =>
        normalizeDashboardLibraryItem(item as Record<string, unknown>, 'saved_dashboard'),
      )
    : [];

  return {
    generatedAt: String(payload.generatedAt ?? payload.generated_at ?? ''),
    systemTemplates,
    savedDashboards,
  };
}

export async function fetchDashboardLibrary(
  signal?: AbortSignal,
): Promise<DashboardLibraryResponse> {
  const payload = await apiClient.get<Record<string, unknown>>('/dashboards/library/', { signal });
  return normalizeDashboardLibraryResponse(payload);
}

export async function fetchReportingCatalog(
  signal?: AbortSignal,
): Promise<ReportingCatalogResponse> {
  return apiClient.get<ReportingCatalogResponse>('/dashboards/reporting-catalog/', { signal });
}

export async function previewDashboardWidget(
  payload: {
    widget: DashboardV1Widget;
    date_range?: Record<string, unknown>;
    client_id?: string;
    account_id?: string;
    page_id?: string;
  },
  signal?: AbortSignal,
): Promise<DashboardWidgetPreviewResponse> {
  return apiClient.post<DashboardWidgetPreviewResponse>('/dashboards/widget-preview/', payload, {
    signal,
  });
}

export async function createDashboardDefinition(
  payload: Pick<
    DashboardDefinition,
    'name' | 'description' | 'template_key' | 'filters' | 'layout' | 'default_metric' | 'is_active'
  >,
): Promise<DashboardDefinition> {
  return apiClient.post<DashboardDefinition>('/dashboards/definitions/', payload);
}

export async function getDashboardDefinition(
  dashboardId: string,
  signal?: AbortSignal,
): Promise<DashboardDefinition> {
  return apiClient.get<DashboardDefinition>(`/dashboards/definitions/${dashboardId}/`, {
    signal,
  });
}

export async function updateDashboardDefinition(
  dashboardId: string,
  payload: Partial<
    Pick<
      DashboardDefinition,
      | 'name'
      | 'description'
      | 'template_key'
      | 'filters'
      | 'layout'
      | 'default_metric'
      | 'is_active'
    >
  >,
): Promise<DashboardDefinition> {
  return apiClient.patch<DashboardDefinition>(`/dashboards/definitions/${dashboardId}/`, payload);
}

export async function deleteDashboardDefinition(dashboardId: string): Promise<void> {
  await apiClient.delete(`/dashboards/definitions/${dashboardId}/`);
}

export async function duplicateDashboardDefinition(
  dashboardId: string,
): Promise<DashboardDefinition> {
  return apiClient.post<DashboardDefinition>(
    `/dashboards/definitions/${dashboardId}/duplicate/`,
    {},
  );
}

export async function fetchSyncHealth(signal?: AbortSignal): Promise<SyncHealthResponse> {
  return apiClient.get<SyncHealthResponse>('/ops/sync-health/', { signal });
}

export async function fetchHealthOverview(signal?: AbortSignal): Promise<HealthOverviewResponse> {
  return apiClient.get<HealthOverviewResponse>('/ops/health-overview/', { signal });
}

export async function listReports(signal?: AbortSignal): Promise<ReportDefinition[]> {
  const data = await apiClient.get<ReportDefinition[] | { results: ReportDefinition[] }>(
    '/reports/',
    { signal },
  );
  return Array.isArray(data) ? data : data.results;
}

export async function createReport(
  payload: Pick<ReportDefinition, 'name' | 'description'> & {
    filters?: Record<string, unknown>;
    layout?: Record<string, unknown>;
    is_active?: boolean;
  },
): Promise<ReportDefinition> {
  return apiClient.post<ReportDefinition>('/reports/', payload);
}

export async function listReportTemplates(
  signal?: AbortSignal,
): Promise<ReportTemplateRegistryResponse> {
  return apiClient.get<ReportTemplateRegistryResponse>('/reports/templates/', { signal });
}

export async function fetchReportDataAvailability(
  query: {
    template_key?: string;
    date_range?: string;
    start_date?: string;
    end_date?: string;
    client_id?: string;
    account_id?: string;
    page_id?: string;
  } = {},
  signal?: AbortSignal,
): Promise<ReportDataAvailabilityResponse> {
  return apiClient.get<ReportDataAvailabilityResponse>(
    appendQueryParams('/reports/data-availability/', query),
    { signal },
  );
}

export async function createReportFromTemplate(payload: {
  template_key: string;
  name?: string;
  description?: string;
  date_range?: string;
  start_date?: string;
  end_date?: string;
  client_id?: string;
}): Promise<ReportDefinition> {
  return apiClient.post<ReportDefinition>('/reports/from-template/', payload);
}

export async function createSlbMonthlyReportTemplate(payload: {
  name?: string;
  description?: string;
  date_range?: string;
  start_date?: string;
  end_date?: string;
  client_id?: string;
}): Promise<ReportDefinition> {
  return apiClient.post<ReportDefinition>('/reports/slb-monthly-template/', payload);
}

export async function getReport(reportId: string, signal?: AbortSignal): Promise<ReportDefinition> {
  return apiClient.get<ReportDefinition>(`/reports/${reportId}/`, { signal });
}

export async function previewReport(
  reportId: string,
  payload: Record<string, unknown> = {},
  signal?: AbortSignal,
): Promise<ReportPreviewResponse> {
  return apiClient.post<ReportPreviewResponse>(`/reports/${reportId}/preview/`, payload, {
    signal,
  });
}

export async function fetchReportDiagnostics(
  reportId: string,
  signal?: AbortSignal,
): Promise<ReportDiagnosticsResponse> {
  return apiClient.get<ReportDiagnosticsResponse>(`/reports/${reportId}/diagnostics/`, {
    signal,
  });
}

export async function updateReport(
  reportId: string,
  payload: Partial<
    Pick<
      ReportDefinition,
      | 'name'
      | 'description'
      | 'filters'
      | 'layout'
      | 'is_active'
      | 'schedule_cron'
      | 'delivery_emails'
    >
  >,
): Promise<ReportDefinition> {
  return apiClient.patch<ReportDefinition>(`/reports/${reportId}/`, payload);
}

export async function toggleReportSchedule(
  reportId: string,
  enabled: boolean,
): Promise<ReportDefinition> {
  return apiClient.post<ReportDefinition>(`/reports/${reportId}/toggle_schedule/`, { enabled });
}

export async function updateReportSchedule(
  reportId: string,
  payload: { schedule_cron?: string; delivery_emails?: string[] },
): Promise<ReportDefinition> {
  return apiClient.patch<ReportDefinition>(`/reports/${reportId}/`, payload);
}

export async function listReportExports(
  reportId: string,
  signal?: AbortSignal,
): Promise<ReportExportJob[]> {
  const data = await apiClient.get<ReportExportJob[] | { results: ReportExportJob[] }>(
    `/reports/${reportId}/exports/`,
    { signal },
  );
  return Array.isArray(data) ? data : data.results;
}

export async function createReportExport(
  reportId: string,
  exportFormat: 'csv' | 'pdf' | 'png',
): Promise<ReportExportJob> {
  return apiClient.post<ReportExportJob>(`/reports/${reportId}/exports/`, {
    export_format: exportFormat,
  });
}

export async function runScheduledReportDryRun(
  reportId: string,
  exportFormat: 'csv' | 'pdf' | 'png' = 'pdf',
): Promise<ReportExportJob> {
  return apiClient.post<ReportExportJob>(`/reports/${reportId}/scheduled-dry-run/`, {
    export_format: exportFormat,
  });
}

export async function downloadReportExport(exportJobId: string) {
  return apiClient.download(`/exports/${exportJobId}/download/`);
}

export async function listAlerts(signal?: AbortSignal): Promise<AlertRule[]> {
  const data = await apiClient.get<AlertRule[] | { results: AlertRule[] }>('/alerts/', { signal });
  return Array.isArray(data) ? data : data.results;
}

export async function getAlert(alertId: string, signal?: AbortSignal): Promise<AlertRule> {
  return apiClient.get<AlertRule>(`/alerts/${alertId}/`, { signal });
}

export type AlertRun = {
  id: string;
  rule_slug: string;
  rule_name: string | null;
  rule_description: string | null;
  severity: string | null;
  status: 'started' | 'success' | 'no_results' | 'partial' | 'failed';
  row_count: number;
  llm_summary: string;
  error_message: string;
  duration_ms: number;
  created_at: string;
  completed_at: string | null;
};

export async function listAlertRuns(
  params: { rule?: string; status?: string } = {},
  signal?: AbortSignal,
): Promise<PaginatedResponse<AlertRun>> {
  const path = appendQueryParams('/alerts/runs/', params);
  return apiClient.get<PaginatedResponse<AlertRun>>(path, { signal });
}

export async function deleteAlert(alertId: string): Promise<void> {
  await apiClient.delete(`/alerts/${alertId}/`);
}

export async function listSummaries(signal?: AbortSignal): Promise<AISummary[]> {
  const data = await apiClient.get<AISummary[] | { results: AISummary[] }>('/summaries/', {
    signal,
  });
  return Array.isArray(data) ? data : data.results;
}

export async function getSummary(summaryId: string, signal?: AbortSignal): Promise<AISummary> {
  return apiClient.get<AISummary>(`/summaries/${summaryId}/`, { signal });
}

export async function refreshSummary(): Promise<AISummary> {
  return apiClient.post<AISummary>('/summaries/refresh/', {});
}

export type NotificationChannel = {
  id: string;
  name: string;
  channel_type: 'email' | 'webhook' | 'slack';
  config: Record<string, unknown>;
  credentials_configured: boolean;
  masked_destination: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export async function listNotificationChannels(
  signal?: AbortSignal,
): Promise<NotificationChannel[]> {
  const data = await apiClient.get<NotificationChannel[] | { results: NotificationChannel[] }>(
    '/notification-channels/',
    { signal },
  );
  return Array.isArray(data) ? data : data.results;
}

export async function createNotificationChannel(
  payload: Pick<NotificationChannel, 'name' | 'channel_type'> & {
    config?: Record<string, unknown>;
    secret_config?: Record<string, unknown>;
    is_active?: boolean;
  },
): Promise<NotificationChannel> {
  return apiClient.post<NotificationChannel>('/notification-channels/', payload);
}

export async function deleteNotificationChannel(channelId: string): Promise<void> {
  await apiClient.delete(`/notification-channels/${channelId}/`);
}

export async function createAlert(
  payload: Pick<
    AlertRule,
    'name' | 'metric' | 'comparison_operator' | 'threshold' | 'lookback_hours' | 'severity'
  > & {
    is_active?: boolean;
    notification_channels?: string[];
  },
): Promise<AlertRule> {
  return apiClient.post<AlertRule>('/alerts/', payload);
}

export async function updateAlert(
  alertId: string,
  payload: Partial<
    Pick<
      AlertRule,
      | 'name'
      | 'metric'
      | 'comparison_operator'
      | 'threshold'
      | 'lookback_hours'
      | 'severity'
      | 'is_active'
      | 'notification_channels'
    >
  >,
): Promise<AlertRule> {
  return apiClient.patch<AlertRule>(`/alerts/${alertId}/`, payload);
}

export async function pauseAlert(
  alertId: string,
  body: { pause_until?: string; duration_hours?: number } = {},
): Promise<AlertRule> {
  return apiClient.post<AlertRule>(`/alerts/${alertId}/pause/`, body);
}

export async function resumeAlert(alertId: string): Promise<AlertRule> {
  return apiClient.post<AlertRule>(`/alerts/${alertId}/resume/`, {});
}

export async function triggerResync(connectionId: string): Promise<void> {
  await apiClient.post(`/ops/sync-health/${connectionId}/resync/`, {});
}

export async function listAuditLogs(
  params: {
    action?: string;
    resource_type?: string;
    page?: number;
    start_date?: string;
    end_date?: string;
  } = {},
  signal?: AbortSignal,
): Promise<PaginatedResponse<AuditLogEntry>> {
  const path = appendQueryParams('/audit-logs/', params);
  return apiClient.get<PaginatedResponse<AuditLogEntry>>(path, { signal });
}

export type UserProfile = {
  user: {
    id: string;
    email: string;
    first_name: string;
    last_name: string;
    tenant: string;
    timezone: string;
    roles: string[];
  };
  tenant_id: string;
};

export async function fetchProfile(signal?: AbortSignal): Promise<UserProfile> {
  return apiClient.get<UserProfile>('/me/', { signal });
}
