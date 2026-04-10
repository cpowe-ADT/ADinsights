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
      item.kind === 'saved_dashboard' || item.kind === 'system_template'
        ? item.kind
        : fallbackKind,
    templateKey: String(item.template_key ?? item.templateKey ?? 'meta_campaign_performance') as DashboardTemplateKey,
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

function normalizeDashboardLibraryResponse(payload: Record<string, unknown>): DashboardLibraryResponse {
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

export async function listDashboardDefinitions(
  signal?: AbortSignal,
): Promise<DashboardDefinition[]> {
  const payload = await apiClient.get<
    DashboardDefinition[] | PaginatedResponse<DashboardDefinition>
  >('/dashboards/definitions/', { signal });
  return Array.isArray(payload) ? payload : payload.results;
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
      'name' | 'description' | 'template_key' | 'filters' | 'layout' | 'default_metric' | 'is_active'
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
  return apiClient.post<DashboardDefinition>(`/dashboards/definitions/${dashboardId}/duplicate/`, {});
}

export async function fetchSyncHealth(signal?: AbortSignal): Promise<SyncHealthResponse> {
  return apiClient.get<SyncHealthResponse>('/ops/sync-health/', { signal });
}

export async function triggerSync(connectionId: string): Promise<{ status: string; connection_id: string }> {
  return apiClient.post<{ status: string; connection_id: string }>(`/airbyte/connections/${connectionId}/trigger-sync/`, {});
}

export async function fetchHealthOverview(signal?: AbortSignal): Promise<HealthOverviewResponse> {
  return apiClient.get<HealthOverviewResponse>('/ops/health-overview/', { signal });
}

export async function listReports(signal?: AbortSignal): Promise<ReportDefinition[]> {
  const data = await apiClient.get<ReportDefinition[] | { results: ReportDefinition[] }>('/reports/', { signal });
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

export async function getReport(reportId: string, signal?: AbortSignal): Promise<ReportDefinition> {
  return apiClient.get<ReportDefinition>(`/reports/${reportId}/`, { signal });
}

export async function listReportExports(
  reportId: string,
  signal?: AbortSignal,
): Promise<ReportExportJob[]> {
  const data = await apiClient.get<ReportExportJob[] | { results: ReportExportJob[] }>(`/reports/${reportId}/exports/`, { signal });
  return Array.isArray(data) ? data : data.results;
}

export async function updateReport(
  reportId: string,
  payload: Partial<Pick<ReportDefinition, 'name' | 'description' | 'is_active' | 'filters' | 'layout'>>,
): Promise<ReportDefinition> {
  return apiClient.patch<ReportDefinition>(`/reports/${reportId}/`, payload);
}

export async function createReportExport(
  reportId: string,
  exportFormat: 'csv' | 'pdf' | 'png',
): Promise<ReportExportJob> {
  return apiClient.post<ReportExportJob>(`/reports/${reportId}/exports/`, {
    export_format: exportFormat,
  });
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

export async function createAlert(
  payload: Pick<AlertRule, 'name' | 'metric' | 'comparison_operator' | 'threshold' | 'lookback_hours' | 'severity'> & { is_active?: boolean },
): Promise<AlertRule> {
  return apiClient.post<AlertRule>('/alerts/', payload);
}

export async function listAlertRuns(
  params: { rule?: string; status?: string } = {},
  signal?: AbortSignal,
): Promise<PaginatedResponse<AlertRun>> {
  const path = appendQueryParams('/alerts/runs/', params);
  return apiClient.get<PaginatedResponse<AlertRun>>(path, { signal });
}

export async function listSummaries(signal?: AbortSignal): Promise<AISummary[]> {
  const data = await apiClient.get<AISummary[] | { results: AISummary[] }>('/summaries/', { signal });
  return Array.isArray(data) ? data : data.results;
}

export async function getSummary(summaryId: string, signal?: AbortSignal): Promise<AISummary> {
  return apiClient.get<AISummary>(`/summaries/${summaryId}/`, { signal });
}

export async function refreshSummary(): Promise<AISummary> {
  return apiClient.post<AISummary>('/summaries/refresh/', {});
}

export async function listAuditLogs(
  params: { action?: string; resource_type?: string; page?: number; start_date?: string; end_date?: string } = {},
  signal?: AbortSignal,
): Promise<PaginatedResponse<AuditLogEntry>> {
  const path = appendQueryParams('/audit-logs/', params);
  return apiClient.get<PaginatedResponse<AuditLogEntry>>(path, { signal });
}
