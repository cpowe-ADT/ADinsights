import apiClient, { appendQueryParams } from './apiClient';

export type DashboardLibraryItem = {
  id: string;
  name: string;
  type: 'Campaigns' | 'Creatives' | 'Budget pacing' | 'Parish map';
  owner: string;
  updatedAt: string;
  tags: string[];
  description: string;
  route: string;
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

export async function fetchDashboardLibrary(signal?: AbortSignal): Promise<DashboardLibraryItem[]> {
  return apiClient.get<DashboardLibraryItem[]>('/dashboards/library/', { signal });
}

export async function fetchSyncHealth(signal?: AbortSignal): Promise<SyncHealthResponse> {
  return apiClient.get<SyncHealthResponse>('/ops/sync-health/', { signal });
}

export async function fetchHealthOverview(signal?: AbortSignal): Promise<HealthOverviewResponse> {
  return apiClient.get<HealthOverviewResponse>('/ops/health-overview/', { signal });
}

export async function listReports(signal?: AbortSignal): Promise<ReportDefinition[]> {
  return apiClient.get<ReportDefinition[]>('/reports/', { signal });
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
  return apiClient.get<ReportExportJob[]>(`/reports/${reportId}/exports/`, { signal });
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
  return apiClient.get<AlertRule[]>('/alerts/', { signal });
}

export async function getAlert(alertId: string, signal?: AbortSignal): Promise<AlertRule> {
  return apiClient.get<AlertRule>(`/alerts/${alertId}/`, { signal });
}

export async function listSummaries(signal?: AbortSignal): Promise<AISummary[]> {
  return apiClient.get<AISummary[]>('/summaries/', { signal });
}

export async function getSummary(summaryId: string, signal?: AbortSignal): Promise<AISummary> {
  return apiClient.get<AISummary>(`/summaries/${summaryId}/`, { signal });
}

export async function refreshSummary(): Promise<AISummary> {
  return apiClient.post<AISummary>('/summaries/refresh/', {});
}

export async function listAuditLogs(
  params: { action?: string; resource_type?: string; page?: number } = {},
  signal?: AbortSignal,
): Promise<PaginatedResponse<AuditLogEntry>> {
  const path = appendQueryParams('/audit-logs/', params);
  return apiClient.get<PaginatedResponse<AuditLogEntry>>(path, { signal });
}
