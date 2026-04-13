import { create } from 'zustand';

import { ApiError, MOCK_MODE, appendQueryParams } from '../lib/apiClient';
import { clearView, loadSavedView, saveView } from '../lib/savedViews';
import {
  fetchBudgetPacing,
  fetchCampaignPerformance,
  fetchCreativePerformance,
  fetchParishAggregates,
  fetchDashboardMetrics,
} from '../lib/dataService';
import {
  areFiltersEqual,
  buildFilterQueryParams,
  createDefaultFilterState,
  normalizeChannelValue,
  serializeFilterQueryParams,
  type FilterBarState,
} from '../lib/dashboardFilters';
import { validate } from '../lib/validate';
import type { SchemaKey } from '../lib/validate';
import {
  clearUploadState,
  loadUploadState,
  saveUploadState,
  buildMetricsFromUpload,
  type UploadedDataset,
} from '../lib/uploadedMetrics';
import {
  getDashboardSessionState,
  resetDashboardSession,
  setDashboardSessionTenant,
  subscribeDashboardSession,
  type DashboardSessionState,
} from './dashboardSession';
import {
  getDatasetMode,
  getLiveDatasetDetail,
  getDatasetSource,
  getDemoTenantId,
  getLiveDatasetReason,
} from './useDatasetStore';
import { messageForLiveDatasetReason } from '../lib/datasetStatus';

export type MetricKey =
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

export type LoadStatus = 'idle' | 'loading' | 'loaded' | 'error';
export type ErrorKind = 'stale_snapshot' | 'network' | 'auth' | 'generic';

export interface CampaignPerformanceSummary {
  currency: string;
  totalSpend: number;
  totalImpressions: number;
  totalReach?: number;
  totalClicks: number;
  totalConversions: number;
  averageRoas: number;
  ctr?: number;
  cpc?: number;
  cpm?: number;
  cpa?: number;
  frequency?: number;
}

export interface CampaignTrendPoint {
  date: string;
  spend: number;
  conversions: number;
  clicks: number;
  impressions: number;
  reach?: number;
  adAccountId?: string;
}

export interface CampaignPerformanceRow {
  id: string;
  adAccountId?: string;
  name: string;
  platform: string;
  status: string;
  objective?: string;
  parishes?: string[];
  spend: number;
  impressions: number;
  reach?: number;
  clicks: number;
  conversions: number;
  roas: number;
  ctr?: number;
  cpc?: number;
  cpm?: number;
  cpa?: number;
  frequency?: number;
  startDate?: string;
  endDate?: string;
}

export interface CampaignPerformanceResponse {
  summary: CampaignPerformanceSummary;
  trend: CampaignTrendPoint[];
  rows: CampaignPerformanceRow[];
}

export interface CreativePerformanceRow {
  id: string;
  adAccountId?: string;
  name: string;
  campaignId: string;
  campaignName: string;
  platform: string;
  parishes?: string[];
  spend: number;
  impressions: number;
  reach?: number;
  clicks: number;
  conversions: number;
  roas: number;
  ctr?: number;
  cpc?: number;
  cpm?: number;
  cpa?: number;
  frequency?: number;
  thumbnailUrl?: string;
  startDate?: string;
  endDate?: string;
}

export interface BudgetPacingRow {
  id: string;
  adAccountId?: string;
  campaignName: string;
  parishes?: string[];
  platform?: string;
  monthlyBudget: number;
  windowBudget?: number;
  windowDays?: number;
  spendToDate: number;
  projectedSpend: number;
  pacingPercent: number;
  startDate?: string;
  endDate?: string;
}

export interface ParishAggregate {
  adAccountId?: string;
  parish: string;
  spend: number;
  impressions: number;
  reach?: number;
  clicks: number;
  conversions: number;
  roas?: number;
  ctr?: number;
  cpc?: number;
  cpm?: number;
  cpa?: number;
  frequency?: number;
  campaignCount?: number;
  currency?: string;
}

export interface AgeBreakdown {
  ageRange: string;
  spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  reach: number;
}

export interface GenderBreakdown {
  gender: string;
  spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  reach: number;
}

export interface AgeGenderBreakdown {
  ageRange: string;
  gender: string;
  spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  reach: number;
}

export interface DemographicsData {
  byAge: AgeBreakdown[];
  byGender: GenderBreakdown[];
  byAgeGender: AgeGenderBreakdown[];
}

export interface PlatformBreakdown {
  platform: string;
  spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  reach: number;
}

export interface DeviceBreakdown {
  device: string;
  spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  reach: number;
}

export interface PlatformDeviceBreakdown {
  platform: string;
  device: string;
  spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  reach: number;
}

export interface PlatformsData {
  byPlatform: PlatformBreakdown[];
  byDevice: DeviceBreakdown[];
  byPlatformDevice: PlatformDeviceBreakdown[];
}

export interface DashboardCoverage {
  startDate?: string | null;
  endDate?: string | null;
}

export interface DashboardSectionAvailability {
  status: 'available' | 'empty' | 'unavailable';
  reason?: string | null;
  coveragePercent?: number | null;
}

export interface DashboardAvailability {
  campaign: DashboardSectionAvailability;
  creative: DashboardSectionAvailability;
  budget: DashboardSectionAvailability;
  parish_map: DashboardSectionAvailability;
}

export interface TenantMetricsSnapshot {
  campaign?: CampaignPerformanceResponse;
  campaigns?: CampaignPerformanceResponse;
  campaign_performance?: CampaignPerformanceResponse;
  creative?: CreativePerformanceRow[];
  creatives?: CreativePerformanceRow[];
  creative_performance?: CreativePerformanceRow[];
  budget?: BudgetPacingRow[];
  budgets?: BudgetPacingRow[];
  budget_pacing?: BudgetPacingRow[];
  parish?: ParishAggregate[];
  parishes?: ParishAggregate[];
  parish_aggregates?: ParishAggregate[];
  tenant_id?: string;
  generated_at?: string;
  snapshot_generated_at?: string;
  demographics?: DemographicsData;
  platforms?: PlatformsData;
  coverage?: DashboardCoverage;
  availability?: DashboardAvailability;
  [key: string]: unknown;
}

export interface TenantMetricsResolved {
  campaign: CampaignPerformanceResponse;
  creative: CreativePerformanceRow[];
  budget: BudgetPacingRow[];
  parish: ParishAggregate[];
  demographics?: DemographicsData;
  platforms?: PlatformsData;
  tenantId?: string;
  currency: string;
  snapshotGeneratedAt?: string;
  coverage?: DashboardCoverage;
  availability?: DashboardAvailability;
}

type AsyncSlice<T> = {
  status: LoadStatus;
  data?: T;
  error?: string;
  errorKind?: ErrorKind;
};

interface DashboardState {
  filters: FilterBarState;
  selectedParish?: string;
  selectedMetric: MetricKey;
  campaign: AsyncSlice<CampaignPerformanceResponse>;
  creative: AsyncSlice<CreativePerformanceRow[]>;
  budget: AsyncSlice<BudgetPacingRow[]>;
  parish: AsyncSlice<ParishAggregate[]>;
  demographics: AsyncSlice<DemographicsData>;
  platforms: AsyncSlice<PlatformsData>;
  activeTenantId?: string;
  activeTenantLabel?: string;
  lastLoadedTenantId?: string;
  lastLoadedFiltersKey?: string;
  lastSnapshotGeneratedAt?: string;
  coverage?: DashboardCoverage;
  availability?: DashboardAvailability;
  metricsCache: Record<string, TenantMetricsResolved>;
  uploadedDataset?: UploadedDataset;
  uploadedActive: boolean;
  setFilters: (filters: FilterBarState) => void;
  setSelectedParish: (parish?: string) => void;
  setSelectedMetric: (metric: MetricKey) => void;
  setActiveTenant: (tenantId?: string, tenantLabel?: string) => void;
  loadAll: (tenantId?: string, options?: { force?: boolean }) => Promise<void>;
  getCachedMetrics: (tenantId?: string) => TenantMetricsResolved | undefined;
  getCampaignRowsForSelectedParish: () => CampaignPerformanceRow[];
  getCreativeRowsForSelectedParish: () => CreativePerformanceRow[];
  getBudgetRowsForSelectedParish: () => BudgetPacingRow[];
  reset: () => void;
  getSavedTableView: <T = unknown>(tableId: string) => T | undefined;
  setSavedTableView: (tableId: string, view: unknown) => void;
  clearSavedTableView: (tableId: string) => void;
  setUploadedDataset: (dataset: UploadedDataset, active?: boolean) => void;
  setUploadedActive: (active: boolean) => void;
  clearUploadedDataset: () => void;
}

const initialSlice = <T>(): AsyncSlice<T> => ({
  status: 'idle',
  data: undefined,
  error: undefined,
  errorKind: undefined,
});

const DEFAULT_TENANT_KEY = '__default__';

function createInitialState(): Pick<
  DashboardState,
  | 'filters'
  | 'selectedParish'
  | 'selectedMetric'
  | 'campaign'
  | 'creative'
  | 'budget'
  | 'parish'
  | 'demographics'
  | 'platforms'
  | 'activeTenantId'
  | 'activeTenantLabel'
  | 'lastLoadedTenantId'
  | 'lastLoadedFiltersKey'
  | 'lastSnapshotGeneratedAt'
  | 'coverage'
  | 'availability'
  | 'metricsCache'
  | 'uploadedDataset'
  | 'uploadedActive'
> {
  const uploadState = loadUploadState();
  const dashboardSession = getDashboardSessionState();
  return {
    filters: createDefaultFilterState(),
    selectedParish: undefined,
    selectedMetric: 'spend',
    campaign: initialSlice(),
    creative: initialSlice(),
    budget: initialSlice(),
    parish: initialSlice(),
    demographics: initialSlice(),
    platforms: initialSlice(),
    activeTenantId: dashboardSession.activeTenantId,
    activeTenantLabel: dashboardSession.activeTenantLabel,
    lastLoadedTenantId: undefined,
    lastLoadedFiltersKey: undefined,
    lastSnapshotGeneratedAt: undefined,
    coverage: undefined,
    availability: undefined,
    metricsCache: {},
    uploadedDataset: uploadState.dataset,
    uploadedActive: uploadState.active,
  };
}

function resolveTenantKey(tenantId?: string, filterKey?: string): string {
  const datasetKey = getDatasetMode();
  return `${tenantId ?? DEFAULT_TENANT_KEY}::${datasetKey}::${filterKey ?? 'default'}`;
}

function resolveFilterKey(filters: FilterBarState): string {
  const serialized = serializeFilterQueryParams(filters);
  return serialized || 'default';
}

export function normalizeParishValue(value: string): string {
  return value
    .toLowerCase()
    .replace(/\./g, '')
    .replace(/\bsaint\b/g, 'st')
    .replace(/\s+/g, ' ')
    .trim();
}

function normalizeFilterQuery(value: string): string {
  return value.trim().toLowerCase();
}

function matchesQuery(value: string | undefined, query: string): boolean {
  if (!query) {
    return true;
  }
  if (!value) {
    return false;
  }
  return value.toLowerCase().includes(query);
}

function resolveChannelFilters(filters: FilterBarState): string[] {
  return filters.channels.map(normalizeChannelValue).filter(Boolean);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function resolveSnapshotSource(snapshot: TenantMetricsSnapshot): TenantMetricsSnapshot {
  if (!isRecord(snapshot)) {
    return snapshot;
  }

  const record = snapshot as Record<string, unknown>;
  const nestedKeys = ['metrics', 'snapshot', 'data', 'results', 'payload'];

  for (const key of nestedKeys) {
    const candidate = record[key];
    if (isRecord(candidate)) {
      return candidate as TenantMetricsSnapshot;
    }
  }

  return snapshot;
}

function normalizeCurrencyCode(value: unknown): string {
  if (typeof value !== 'string') {
    throw new Error('Currency code is missing or invalid');
  }

  const trimmed = value.trim();
  if (!trimmed) {
    throw new Error('Currency code is empty');
  }

  return trimmed.toUpperCase();
}

function normalizeTenantId(value: unknown): string | undefined {
  if (typeof value === 'string') {
    const trimmed = value.trim();
    return trimmed ? trimmed : undefined;
  }

  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(value);
  }

  return undefined;
}

function extractTenantId(snapshot: TenantMetricsSnapshot, fallback?: string): string | undefined {
  if (!isRecord(snapshot)) {
    return fallback;
  }

  const searchKeys = ['tenant_id', 'tenantId', 'tenant', 'tenantID'];
  for (const key of searchKeys) {
    const candidate = normalizeTenantId(snapshot[key]);
    if (candidate) {
      return candidate;
    }
  }

  const metadata = snapshot['metadata'];
  if (isRecord(metadata)) {
    for (const key of searchKeys) {
      const candidate = normalizeTenantId(metadata[key]);
      if (candidate) {
        return candidate;
      }
    }
  }

  return fallback;
}

function extractSnapshotTimestamp(
  snapshot: TenantMetricsSnapshot,
  fallback?: string,
): string | undefined {
  if (!isRecord(snapshot)) {
    return fallback;
  }
  const keys = ['snapshot_generated_at', 'snapshotGeneratedAt', 'generated_at', 'generatedAt'];
  for (const key of keys) {
    const value = snapshot[key];
    if (typeof value === 'string' && value.trim()) {
      return value;
    }
  }
  const metadata = snapshot['metadata'];
  if (isRecord(metadata)) {
    for (const key of keys) {
      const value = metadata[key];
      if (typeof value === 'string' && value.trim()) {
        return value;
      }
    }
  }
  return fallback;
}

function normalizeCoverage(value: unknown): DashboardCoverage | undefined {
  if (!isRecord(value)) {
    return undefined;
  }

  const startDate =
    typeof value.startDate === 'string'
      ? value.startDate
      : typeof value.start_date === 'string'
        ? value.start_date
        : null;
  const endDate =
    typeof value.endDate === 'string'
      ? value.endDate
      : typeof value.end_date === 'string'
        ? value.end_date
        : null;

  if (!startDate && !endDate) {
    return undefined;
  }

  return { startDate, endDate };
}

function normalizeSectionAvailability(value: unknown): DashboardSectionAvailability | undefined {
  if (!isRecord(value)) {
    return undefined;
  }

  const status = value.status;
  if (status !== 'available' && status !== 'empty' && status !== 'unavailable') {
    return undefined;
  }

  return {
    status,
    reason: typeof value.reason === 'string' ? value.reason : null,
    coveragePercent:
      typeof value.coverage_percent === 'number'
        ? value.coverage_percent
        : typeof value.coveragePercent === 'number'
          ? value.coveragePercent
          : null,
  };
}

function normalizeAvailability(value: unknown): DashboardAvailability | undefined {
  if (!isRecord(value)) {
    return undefined;
  }

  const campaign = normalizeSectionAvailability(value.campaign);
  const creative = normalizeSectionAvailability(value.creative);
  const budget = normalizeSectionAvailability(value.budget);
  const parishMap = normalizeSectionAvailability(value.parish_map ?? value.parishMap);
  if (!campaign || !creative || !budget || !parishMap) {
    return undefined;
  }

  return {
    campaign,
    creative,
    budget,
    parish_map: parishMap,
  };
}

function assertValidSchema<T>(schema: SchemaKey, payload: T, message: string): T {
  const valid = validate(schema, payload);
  if (!valid) {
    throw new Error(message);
  }
  return payload;
}

function ensureArray<T>(value: unknown, message: string): T[] {
  if (typeof value === 'undefined' || value === null) {
    return [];
  }

  if (Array.isArray(value)) {
    return value as T[];
  }

  throw new Error(message);
}

function normalizeCampaignResponse(
  response: CampaignPerformanceResponse,
): CampaignPerformanceResponse {
  const currency = normalizeCurrencyCode(response.summary.currency);
  return {
    ...response,
    summary: {
      ...response.summary,
      currency,
    },
  };
}

function determineParishCurrency(rows: ParishAggregate[], fallback?: string): string {
  if (typeof fallback === 'string' && fallback.trim()) {
    return normalizeCurrencyCode(fallback);
  }

  for (const row of rows) {
    if (typeof row.currency === 'string' && row.currency.trim()) {
      return normalizeCurrencyCode(row.currency);
    }
  }

  throw new Error('Parish aggregates missing currency information');
}

function normalizeParishAggregates(
  rows: ParishAggregate[],
  currencyHint?: string,
): ParishAggregate[] {
  const currency = determineParishCurrency(rows, currencyHint);
  return rows.map((row) => {
    if (typeof row.currency === 'string') {
      const rowCurrency = normalizeCurrencyCode(row.currency);
      if (rowCurrency !== currency) {
        console.warn(
          `Parish currency mismatch detected (expected ${currency}, received ${rowCurrency}). Normalizing to ${currency}.`,
        );
      }
    }

    return {
      ...row,
      currency,
    };
  });
}

function normalizeResolvedMetrics(input: {
  campaign: CampaignPerformanceResponse;
  creative: CreativePerformanceRow[];
  budget: BudgetPacingRow[];
  parish: ParishAggregate[];
  demographics?: DemographicsData;
  platforms?: PlatformsData;
  tenantId?: string;
  snapshotGeneratedAt?: string;
  coverage?: DashboardCoverage;
  availability?: DashboardAvailability;
}): TenantMetricsResolved {
  const campaign = normalizeCampaignResponse(input.campaign);
  const parish = normalizeParishAggregates(input.parish, campaign.summary.currency);
  const currency = campaign.summary.currency;

  return {
    campaign,
    creative: input.creative,
    budget: input.budget,
    parish,
    demographics: input.demographics,
    platforms: input.platforms,
    tenantId: input.tenantId,
    currency,
    snapshotGeneratedAt: input.snapshotGeneratedAt,
    coverage: input.coverage,
    availability: input.availability,
  };
}

function parseTenantMetrics(snapshot: TenantMetricsSnapshot): TenantMetricsResolved {
  const source = resolveSnapshotSource(snapshot);
  const record = source as Record<string, unknown>;

  const campaign =
    source.campaign ??
    source.campaigns ??
    source.campaign_performance ??
    (record['campaign_metrics'] as CampaignPerformanceResponse | undefined) ??
    (record['campaignMetrics'] as CampaignPerformanceResponse | undefined) ??
    (record['campaignPerformance'] as CampaignPerformanceResponse | undefined);

  if (!campaign) {
    throw new Error('Campaign metrics missing from aggregated response');
  }

  const creative =
    source.creative ??
    source.creatives ??
    source.creative_performance ??
    (record['creative_metrics'] as CreativePerformanceRow[] | undefined) ??
    (record['creativeMetrics'] as CreativePerformanceRow[] | undefined) ??
    (record['creativePerformance'] as CreativePerformanceRow[] | undefined) ??
    [];

  const budget =
    source.budget ??
    source.budgets ??
    source.budget_pacing ??
    (record['budget_metrics'] as BudgetPacingRow[] | undefined) ??
    (record['budgetMetrics'] as BudgetPacingRow[] | undefined) ??
    (record['budgetPacing'] as BudgetPacingRow[] | undefined) ??
    [];

  const parish =
    source.parish ??
    source.parishes ??
    source.parish_aggregates ??
    (record['parish_metrics'] as ParishAggregate[] | undefined) ??
    (record['parishMetrics'] as ParishAggregate[] | undefined) ??
    (record['parishAggregates'] as ParishAggregate[] | undefined) ??
    [];

  const demographics: DemographicsData | undefined =
    source.demographics ??
    (record['demographics'] as DemographicsData | undefined);

  const platforms: PlatformsData | undefined =
    source.platforms ??
    (record['platforms'] as PlatformsData | undefined);

  const normalizedCampaign = assertValidSchema(
    'metrics',
    campaign,
    'Campaign metrics invalid in aggregated response',
  );
  const normalizedCreative = assertValidSchema(
    'creative',
    ensureArray<CreativePerformanceRow>(
      creative,
      'Creative metrics invalid in aggregated response',
    ),
    'Creative metrics invalid in aggregated response',
  );
  const normalizedBudget = assertValidSchema(
    'budget',
    ensureArray<BudgetPacingRow>(budget, 'Budget metrics invalid in aggregated response'),
    'Budget metrics invalid in aggregated response',
  );
  const normalizedParish = assertValidSchema(
    'parish',
    ensureArray<ParishAggregate>(parish, 'Parish metrics invalid in aggregated response'),
    'Parish metrics invalid in aggregated response',
  );

  return normalizeResolvedMetrics({
    campaign: normalizedCampaign,
    creative: normalizedCreative,
    budget: normalizedBudget,
    parish: normalizedParish,
    tenantId: extractTenantId(source, extractTenantId(snapshot)),
    snapshotGeneratedAt: extractSnapshotTimestamp(
      source,
      extractSnapshotTimestamp(snapshot, snapshot.generated_at),
    ),
    coverage: normalizeCoverage(record['coverage'] ?? snapshot['coverage']),
    availability: normalizeAvailability(record['availability'] ?? snapshot['availability']),
    demographics,
    platforms,
  });
}

function withTenant(path: string, tenantId?: string): string {
  if (!tenantId) {
    return path;
  }
  return appendQueryParams(path, { tenant_id: tenantId });
}

function withSource(path: string, source?: string | undefined): string {
  if (!source) {
    return path;
  }
  return appendQueryParams(path, { source });
}

function withQueryParam(path: string, key: string, value?: string): string {
  if (!value) {
    return path;
  }
  return appendQueryParams(path, { [key]: value });
}

function withFilters(path: string, filters: FilterBarState): string {
  return appendQueryParams(path, buildFilterQueryParams(filters));
}

function mapError(reason: unknown): { message: string; kind: ErrorKind } {
  if (reason instanceof ApiError) {
    if (
      reason.status === 503 &&
      reason.payload?.code === 'warehouse_snapshot_unavailable' &&
      reason.payload?.reason === 'stale_snapshot'
    ) {
      return {
        message: 'Dashboard data is temporarily unavailable. The data snapshot is being refreshed.',
        kind: 'stale_snapshot',
      };
    }
    if (
      reason.payload?.code === 'warehouse_snapshot_unavailable' &&
      (reason.payload?.reason === 'missing_snapshot' ||
        reason.payload?.reason === 'default_snapshot')
    ) {
      return {
        message: messageForLiveDatasetReason(
          reason.payload.reason,
          getLiveDatasetDetail(),
        ),
        kind: 'generic',
      };
    }
    if (
      (reason.status === 400 && reason.message === "Unknown adapter 'warehouse'.") ||
      (reason.status === 503 &&
        reason.message === 'Explicit source is required when the warehouse adapter is unavailable.')
    ) {
      return {
        message: messageForLiveDatasetReason(
          getLiveDatasetReason() ?? 'adapter_disabled',
          getLiveDatasetDetail(),
        ),
        kind: 'generic',
      };
    }
    if (reason.status === 401 || reason.status === 403) {
      return {
        message: reason.message || 'Your session has expired. Please sign in again.',
        kind: 'auth',
      };
    }
    return {
      message: reason.message || 'Unable to load the latest insights. Please try again.',
      kind: 'generic',
    };
  }

  if (reason instanceof TypeError) {
    return {
      message: 'Unable to connect. Check your network and try again.',
      kind: 'network',
    };
  }

  if (reason instanceof Error) {
    if (/failed to fetch|network|load failed/i.test(reason.message)) {
      return {
        message: 'Unable to connect. Check your network and try again.',
        kind: 'network',
      };
    }
    if (
      reason.message === "Unknown adapter 'warehouse'." ||
      reason.message === 'Explicit source is required when the warehouse adapter is unavailable.'
    ) {
      return {
        message: messageForLiveDatasetReason(
          getLiveDatasetReason() ?? 'adapter_disabled',
          getLiveDatasetDetail(),
        ),
        kind: 'generic',
      };
    }
    return { message: reason.message, kind: 'generic' };
  }
  return { message: 'Unable to load the latest insights. Please try again.', kind: 'generic' };
}

async function fetchDummySnapshot(path = '/sample_metrics.json'): Promise<TenantMetricsSnapshot> {
  const response = await fetch(path, { credentials: 'same-origin' });
  if (!response.ok) {
    throw new Error('Unable to load demo metrics snapshot.');
  }
  return (await response.json()) as TenantMetricsSnapshot;
}

function applySessionStateToDashboard(
  state: DashboardState,
  session: DashboardSessionState,
): Partial<DashboardState> | null {
  const currentTenantId = normalizeTenantId(state.activeTenantId);
  const nextTenantId = normalizeTenantId(session.activeTenantId);
  const nextTenantLabel =
    typeof session.activeTenantLabel === 'string' && session.activeTenantLabel.trim()
      ? session.activeTenantLabel.trim()
      : undefined;
  const tenantChanged = currentTenantId !== nextTenantId;
  const labelChanged = state.activeTenantLabel !== nextTenantLabel;

  if (!tenantChanged && !labelChanged) {
    return null;
  }

  return {
    activeTenantId: nextTenantId,
    activeTenantLabel: nextTenantLabel ?? (tenantChanged ? undefined : state.activeTenantLabel),
    selectedParish: tenantChanged ? undefined : state.selectedParish,
  };
}

const useDashboardStore = create<DashboardState>((set, get) => ({
  ...createInitialState(),
  getSavedTableView: (tableId) => loadSavedView(tableId),
  setSavedTableView: (tableId, view) => saveView(tableId, view),
  clearSavedTableView: (tableId) => clearView(tableId),
  setUploadedDataset: (dataset, active = true) => {
    saveUploadState(dataset, active);
    set((state) => ({
      uploadedDataset: dataset,
      uploadedActive: active,
      metricsCache: {},
      lastLoadedFiltersKey: undefined,
      lastLoadedTenantId: undefined,
      lastSnapshotGeneratedAt: state.lastSnapshotGeneratedAt,
      coverage: undefined,
      availability: undefined,
    }));
  },
  setUploadedActive: (active) => {
    const { uploadedDataset } = get();
    if (uploadedDataset) {
      saveUploadState(uploadedDataset, active);
    }
    set((state) => ({
      uploadedActive: active,
      metricsCache: {},
      lastLoadedFiltersKey: undefined,
      lastLoadedTenantId: undefined,
      lastSnapshotGeneratedAt: state.lastSnapshotGeneratedAt,
      coverage: undefined,
      availability: undefined,
    }));
  },
  clearUploadedDataset: () => {
    clearUploadState();
    set((state) => ({
      uploadedDataset: undefined,
      uploadedActive: false,
      metricsCache: {},
      lastLoadedFiltersKey: undefined,
      lastLoadedTenantId: undefined,
      lastSnapshotGeneratedAt: state.lastSnapshotGeneratedAt,
      coverage: undefined,
      availability: undefined,
    }));
  },
  setFilters: (nextFilters) => {
    const current = get().filters;
    if (areFiltersEqual(current, nextFilters)) {
      return;
    }
    set({ filters: nextFilters });
  },
  setSelectedParish: (parish) => {
    if (!parish) {
      set({ selectedParish: undefined });
      return;
    }
    const normalizedNext = normalizeParishValue(parish);
    const current = get().selectedParish;
    const normalizedCurrent = current ? normalizeParishValue(current) : '';
    set({
      selectedParish: normalizedCurrent === normalizedNext ? undefined : parish.trim(),
    });
  },
  setSelectedMetric: (metric) => set({ selectedMetric: metric }),
  setActiveTenant: (tenantId, tenantLabel) => {
    setDashboardSessionTenant(tenantId, tenantLabel);
  },
  loadAll: async (tenantId, options) => {
    const {
      campaign,
      creative,
      budget,
      parish,
      activeTenantId,
      lastLoadedTenantId,
      lastLoadedFiltersKey,
      filters,
      metricsCache,
    } = get();
    const requestedTenantId =
      typeof tenantId === 'undefined' ? activeTenantId : (tenantId ?? activeTenantId);
    const normalizedTenantId = normalizeTenantId(requestedTenantId);
    const filterKey = resolveFilterKey(filters);
    const tenantKey = resolveTenantKey(normalizedTenantId, filterKey);
    const cachedMetrics = metricsCache[tenantKey];
    const { uploadedDataset, uploadedActive } = get();
    const normalizedLastLoaded = normalizeTenantId(lastLoadedTenantId);
    const isTenantChange =
      typeof normalizedTenantId !== 'undefined' && normalizedTenantId !== normalizedLastLoaded;
    const isFilterChange = filterKey !== lastLoadedFiltersKey;
    const isQueryChange = isTenantChange || isFilterChange;
    const allSlicesLoaded =
      campaign.status === 'loaded' &&
      creative.status === 'loaded' &&
      budget.status === 'loaded' &&
      parish.status === 'loaded';

    const hasUploadOverride = uploadedActive && uploadedDataset;
    if (!options?.force && !hasUploadOverride) {
      if (!isQueryChange && allSlicesLoaded) {
        return;
      }

      if (cachedMetrics && isQueryChange) {
        set((state) => ({
          activeTenantId: cachedMetrics.tenantId ?? normalizedTenantId ?? state.activeTenantId,
          lastLoadedTenantId:
            cachedMetrics.tenantId ?? normalizedTenantId ?? state.lastLoadedTenantId,
          lastLoadedFiltersKey: filterKey,
          lastSnapshotGeneratedAt:
            cachedMetrics.snapshotGeneratedAt ?? state.lastSnapshotGeneratedAt,
          coverage: cachedMetrics.coverage ?? state.coverage,
          availability: cachedMetrics.availability ?? state.availability,
          selectedParish: isTenantChange ? undefined : state.selectedParish,
          campaign: {
            status: 'loaded',
            data: cachedMetrics.campaign,
            error: undefined,
            errorKind: undefined,
          },
          creative: {
            status: 'loaded',
            data: cachedMetrics.creative,
            error: undefined,
            errorKind: undefined,
          },
          budget: {
            status: 'loaded',
            data: cachedMetrics.budget,
            error: undefined,
            errorKind: undefined,
          },
          parish: {
            status: 'loaded',
            data: cachedMetrics.parish,
            error: undefined,
            errorKind: undefined,
          },
        }));
        return;
      }

      if (cachedMetrics && !isQueryChange && !allSlicesLoaded) {
        set((state) => ({
          activeTenantId: cachedMetrics.tenantId ?? state.activeTenantId,
          lastLoadedTenantId: cachedMetrics.tenantId ?? state.lastLoadedTenantId,
          lastLoadedFiltersKey: filterKey,
          lastSnapshotGeneratedAt:
            cachedMetrics.snapshotGeneratedAt ?? state.lastSnapshotGeneratedAt,
          coverage: cachedMetrics.coverage ?? state.coverage,
          availability: cachedMetrics.availability ?? state.availability,
          campaign: {
            status: 'loaded',
            data: cachedMetrics.campaign,
            error: undefined,
            errorKind: undefined,
          },
          creative: {
            status: 'loaded',
            data: cachedMetrics.creative,
            error: undefined,
            errorKind: undefined,
          },
          budget: {
            status: 'loaded',
            data: cachedMetrics.budget,
            error: undefined,
            errorKind: undefined,
          },
          parish: {
            status: 'loaded',
            data: cachedMetrics.parish,
            error: undefined,
            errorKind: undefined,
          },
        }));
        return;
      }
    }

    set((state) => ({
      activeTenantId: normalizedTenantId ?? state.activeTenantId,
      lastLoadedTenantId: state.lastLoadedTenantId,
      selectedParish: isTenantChange ? undefined : state.selectedParish,
      campaign: { ...state.campaign, status: 'loading', error: undefined, errorKind: undefined },
      creative: { ...state.creative, status: 'loading', error: undefined, errorKind: undefined },
      budget: { ...state.budget, status: 'loading', error: undefined, errorKind: undefined },
      parish: { ...state.parish, status: 'loading', error: undefined, errorKind: undefined },
      demographics: { ...state.demographics, status: 'loading', error: undefined, errorKind: undefined },
      platforms: { ...state.platforms, status: 'loading', error: undefined, errorKind: undefined },
    }));

    if (uploadedActive && uploadedDataset) {
      try {
        const resolved = buildMetricsFromUpload(uploadedDataset, filters, normalizedTenantId);
        set((state) => ({
          activeTenantId: resolved.tenantId ?? state.activeTenantId,
          lastLoadedTenantId: resolved.tenantId ?? normalizedTenantId ?? state.lastLoadedTenantId,
          lastLoadedFiltersKey: filterKey,
          lastSnapshotGeneratedAt: resolved.snapshotGeneratedAt ?? state.lastSnapshotGeneratedAt,
          coverage: resolved.coverage ?? state.coverage,
          availability: resolved.availability ?? state.availability,
          campaign: { status: 'loaded', data: resolved.campaign, error: undefined, errorKind: undefined },
          creative: { status: 'loaded', data: resolved.creative, error: undefined, errorKind: undefined },
          budget: { status: 'loaded', data: resolved.budget, error: undefined, errorKind: undefined },
          parish: { status: 'loaded', data: resolved.parish, error: undefined, errorKind: undefined },
          demographics: { status: 'loaded', data: resolved.demographics, error: undefined, errorKind: undefined },
          platforms: { status: 'loaded', data: resolved.platforms, error: undefined, errorKind: undefined },
          metricsCache: { ...state.metricsCache, [tenantKey]: resolved },
        }));
      } catch (error) {
        const { message, kind } = mapError(error);
        set((state) => ({
          campaign: { status: 'error', data: state.campaign.data, error: message, errorKind: kind },
          creative: { status: 'error', data: state.creative.data, error: message, errorKind: kind },
          budget: { status: 'error', data: state.budget.data, error: message, errorKind: kind },
          parish: { status: 'error', data: state.parish.data, error: message, errorKind: kind },
          demographics: { status: 'error', data: state.demographics.data, error: message, errorKind: kind },
          platforms: { status: 'error', data: state.platforms.data, error: message, errorKind: kind },
        }));
      }
      return;
    }

    const datasetMode = getDatasetMode();
    const sourceOverride = getDatasetSource();
    const uploadSource = uploadedActive ? 'upload' : undefined;
    const metricsSource = uploadSource ?? sourceOverride;

    if (!MOCK_MODE && !metricsSource) {
      const message =
        datasetMode === 'live'
          ? messageForLiveDatasetReason(
              getLiveDatasetReason() ?? 'adapter_disabled',
              getLiveDatasetDetail(),
            )
          : 'Demo dataset is unavailable.';
      set((state) => ({
        campaign: { status: 'error', data: state.campaign.data, error: message, errorKind: 'generic' },
        creative: { status: 'error', data: state.creative.data, error: message, errorKind: 'generic' },
        budget: { status: 'error', data: state.budget.data, error: message, errorKind: 'generic' },
        parish: { status: 'error', data: state.parish.data, error: message, errorKind: 'generic' },
        demographics: { status: 'error', data: state.demographics.data, error: message, errorKind: 'generic' },
        platforms: { status: 'error', data: state.platforms.data, error: message, errorKind: 'generic' },
      }));
      return;
    }

    let metricsPath = withFilters(
      withSource(withTenant('/metrics/combined/', normalizedTenantId), metricsSource),
      filters,
    );
    if (metricsSource === 'demo') {
      metricsPath = withQueryParam(metricsPath, 'demo_tenant', getDemoTenantId());
    }

    if (!MOCK_MODE && (datasetMode !== 'dummy' || uploadedActive)) {
      try {
        const snapshot = await fetchDashboardMetrics({
          path: metricsPath,
          mockPath: '/sample_metrics.json',
        });
        const resolved = parseTenantMetrics(snapshot);

        set((state) => ({
          activeTenantId: resolved.tenantId ?? state.activeTenantId,
          lastLoadedTenantId: resolved.tenantId ?? normalizedTenantId ?? state.lastLoadedTenantId,
          lastLoadedFiltersKey: filterKey,
          lastSnapshotGeneratedAt: resolved.snapshotGeneratedAt ?? state.lastSnapshotGeneratedAt,
          coverage: resolved.coverage ?? state.coverage,
          availability: resolved.availability ?? state.availability,
          campaign: { status: 'loaded', data: resolved.campaign, error: undefined, errorKind: undefined },
          creative: { status: 'loaded', data: resolved.creative, error: undefined, errorKind: undefined },
          budget: { status: 'loaded', data: resolved.budget, error: undefined, errorKind: undefined },
          parish: { status: 'loaded', data: resolved.parish, error: undefined, errorKind: undefined },
          demographics: { status: 'loaded', data: resolved.demographics, error: undefined, errorKind: undefined },
          platforms: { status: 'loaded', data: resolved.platforms, error: undefined, errorKind: undefined },
          metricsCache: { ...state.metricsCache, [tenantKey]: resolved },
        }));
      } catch (error) {
        const { message, kind } = mapError(error);
        set((state) => ({
          campaign: { status: 'error', data: state.campaign.data, error: message, errorKind: kind },
          creative: { status: 'error', data: state.creative.data, error: message, errorKind: kind },
          budget: { status: 'error', data: state.budget.data, error: message, errorKind: kind },
          parish: { status: 'error', data: state.parish.data, error: message, errorKind: kind },
          demographics: { status: 'error', data: state.demographics.data, error: message, errorKind: kind },
          platforms: { status: 'error', data: state.platforms.data, error: message, errorKind: kind },
        }));
      }

      return;
    }

    if (datasetMode === 'dummy' && !uploadedActive) {
      try {
        if (!MOCK_MODE && metricsSource) {
          const snapshot = await fetchDashboardMetrics({
            path: metricsPath,
            mockPath: '/sample_metrics.json',
          });
          const resolved = parseTenantMetrics(snapshot);

          set((state) => ({
            activeTenantId: resolved.tenantId ?? state.activeTenantId,
            lastLoadedTenantId: resolved.tenantId ?? normalizedTenantId ?? state.lastLoadedTenantId,
            lastLoadedFiltersKey: filterKey,
            lastSnapshotGeneratedAt: resolved.snapshotGeneratedAt ?? state.lastSnapshotGeneratedAt,
            coverage: resolved.coverage ?? state.coverage,
            availability: resolved.availability ?? state.availability,
            campaign: { status: 'loaded', data: resolved.campaign, error: undefined, errorKind: undefined },
            creative: { status: 'loaded', data: resolved.creative, error: undefined, errorKind: undefined },
            budget: { status: 'loaded', data: resolved.budget, error: undefined, errorKind: undefined },
            parish: { status: 'loaded', data: resolved.parish, error: undefined, errorKind: undefined },
          demographics: { status: 'loaded', data: resolved.demographics, error: undefined, errorKind: undefined },
          platforms: { status: 'loaded', data: resolved.platforms, error: undefined, errorKind: undefined },
            metricsCache: { ...state.metricsCache, [tenantKey]: resolved },
          }));
          return;
        }

        let dummyPath = '/sample_metrics.json';
        if (metricsSource) {
          dummyPath = withSource(dummyPath, metricsSource);
        }
        dummyPath = withFilters(dummyPath, filters);
        if (metricsSource === 'demo') {
          dummyPath = withQueryParam(dummyPath, 'demo_tenant', getDemoTenantId());
        }

        const snapshot = await fetchDummySnapshot(dummyPath);
        const resolved = parseTenantMetrics(snapshot);

        set((state) => ({
          activeTenantId: resolved.tenantId ?? state.activeTenantId,
          lastLoadedTenantId: resolved.tenantId ?? normalizedTenantId ?? state.lastLoadedTenantId,
          lastLoadedFiltersKey: filterKey,
          lastSnapshotGeneratedAt: resolved.snapshotGeneratedAt ?? state.lastSnapshotGeneratedAt,
          coverage: resolved.coverage ?? state.coverage,
          availability: resolved.availability ?? state.availability,
          campaign: { status: 'loaded', data: resolved.campaign, error: undefined, errorKind: undefined },
          creative: { status: 'loaded', data: resolved.creative, error: undefined, errorKind: undefined },
          budget: { status: 'loaded', data: resolved.budget, error: undefined, errorKind: undefined },
          parish: { status: 'loaded', data: resolved.parish, error: undefined, errorKind: undefined },
          demographics: { status: 'loaded', data: resolved.demographics, error: undefined, errorKind: undefined },
          platforms: { status: 'loaded', data: resolved.platforms, error: undefined, errorKind: undefined },
          metricsCache: { ...state.metricsCache, [tenantKey]: resolved },
        }));
      } catch (error) {
        const { message, kind } = mapError(error);
        set((state) => ({
          campaign: { status: 'error', data: state.campaign.data, error: message, errorKind: kind },
          creative: { status: 'error', data: state.creative.data, error: message, errorKind: kind },
          budget: { status: 'error', data: state.budget.data, error: message, errorKind: kind },
          parish: { status: 'error', data: state.parish.data, error: message, errorKind: kind },
          demographics: { status: 'error', data: state.demographics.data, error: message, errorKind: kind },
          platforms: { status: 'error', data: state.platforms.data, error: message, errorKind: kind },
        }));
      }

      return;
    }

    const campaignPath = withFilters(
      withSource(withTenant('/analytics/campaign-performance/', tenantId), sourceOverride),
      filters,
    );
    const creativePath = withFilters(
      withSource(withTenant('/analytics/creative-performance/', tenantId), sourceOverride),
      filters,
    );
    const budgetPath = withFilters(
      withSource(withTenant('/analytics/budget-pacing/', tenantId), sourceOverride),
      filters,
    );
    const parishPath = withFilters(
      withSource(withTenant('/analytics/parish-performance/', tenantId), sourceOverride),
      filters,
    );

    const [campaignResult, creativeResult, budgetResult, parishResult] = await Promise.allSettled([
      fetchCampaignPerformance({
        path: campaignPath,
        mockPath: '/sample_campaign_performance.json',
      }),
      fetchCreativePerformance({
        path: creativePath,
        mockPath: '/sample_creative_performance.json',
      }),
      fetchBudgetPacing({
        path: budgetPath,
        mockPath: '/sample_budget_pacing.json',
      }),
      fetchParishAggregates({
        path: parishPath,
        mockPath: '/sample_parish_aggregates.json',
      }),
    ]);

    const normalizedCampaign =
      campaignResult.status === 'fulfilled'
        ? normalizeCampaignResponse(campaignResult.value)
        : undefined;
    const normalizedCreative =
      creativeResult.status === 'fulfilled' ? creativeResult.value : undefined;
    const normalizedBudget = budgetResult.status === 'fulfilled' ? budgetResult.value : undefined;
    let normalizedParish: ParishAggregate[] | undefined;
    let normalizedParishError: unknown;
    if (parishResult.status === 'fulfilled') {
      try {
        normalizedParish = normalizeParishAggregates(
          parishResult.value,
          normalizedCampaign?.summary.currency,
        );
      } catch (error) {
        normalizedParishError = error;
        console.error('Failed to normalize parish aggregates', error);
      }
    }
    const resolvedTenantId = normalizeTenantId(normalizedTenantId);
    let normalizedResolved: TenantMetricsResolved | undefined;
    if (normalizedCampaign && normalizedCreative && normalizedBudget && normalizedParish) {
      try {
        normalizedResolved = normalizeResolvedMetrics({
          campaign: normalizedCampaign,
          creative: normalizedCreative,
          budget: normalizedBudget,
          parish: normalizedParish,
          tenantId: resolvedTenantId,
        });
      } catch (error) {
        normalizedParishError = normalizedParishError ?? error;
        console.error('Failed to normalize aggregate snapshot payload', error);
        normalizedResolved = undefined;
      }
    }

    set((state) => {
      const updatedCache = normalizedResolved
        ? {
            ...state.metricsCache,
            [tenantKey]: normalizedResolved,
          }
        : state.metricsCache;
      const parishErrorReason =
        normalizedParishError ??
        (parishResult.status === 'rejected' ? parishResult.reason : undefined);

      return {
        activeTenantId: normalizedResolved?.tenantId ?? normalizedTenantId ?? state.activeTenantId,
        lastLoadedTenantId:
          normalizedResolved?.tenantId ?? normalizedTenantId ?? state.lastLoadedTenantId,
        lastLoadedFiltersKey: normalizedResolved ? filterKey : state.lastLoadedFiltersKey,
        lastSnapshotGeneratedAt:
          normalizedResolved?.snapshotGeneratedAt ?? state.lastSnapshotGeneratedAt,
        coverage: normalizedResolved?.coverage ?? state.coverage,
        availability: normalizedResolved?.availability ?? state.availability,
        campaign:
          campaignResult.status === 'fulfilled'
            ? { status: 'loaded', data: normalizedCampaign!, error: undefined, errorKind: undefined }
            : {
                status: 'error',
                data: state.campaign.data,
                ...mapError(campaignResult.reason),
              },
        creative:
          creativeResult.status === 'fulfilled'
            ? { status: 'loaded', data: normalizedCreative!, error: undefined, errorKind: undefined }
            : {
                status: 'error',
                data: state.creative.data,
                ...mapError(creativeResult.reason),
              },
        budget:
          budgetResult.status === 'fulfilled'
            ? { status: 'loaded', data: normalizedBudget!, error: undefined, errorKind: undefined }
            : {
                status: 'error',
                data: state.budget.data,
                ...mapError(budgetResult.reason),
              },
        parish: normalizedParish
          ? { status: 'loaded', data: normalizedParish, error: undefined, errorKind: undefined }
          : {
              status: 'error',
              data: state.parish.data,
              ...mapError(parishErrorReason),
            },
        metricsCache: updatedCache,
      };
    });
  },
  getCachedMetrics: (tenantId) => {
    const state = get();
    const normalizedTenantId = normalizeTenantId(tenantId ?? state.activeTenantId);
    const filterKey = resolveFilterKey(state.filters);
    const tenantKey = resolveTenantKey(normalizedTenantId, filterKey);
    return state.metricsCache[tenantKey];
  },
  getCampaignRowsForSelectedParish: () => {
    const { campaign: campaignSlice, selectedParish, filters } = get();
    const rows = campaignSlice.data?.rows ?? [];
    const query = normalizeFilterQuery(filters.campaignQuery);
    const channelFilters = resolveChannelFilters(filters);
    if (!selectedParish) {
      return rows.filter((row) => {
        if (channelFilters.length > 0) {
          const platformKey = normalizeChannelValue(row.platform ?? '');
          if (!platformKey || !channelFilters.includes(platformKey)) {
            return false;
          }
        }
        return matchesQuery(row.name, query);
      });
    }
    const parishKey = normalizeParishValue(selectedParish);
    return rows.filter((row) => {
      if (!row.parishes?.some((parish) => normalizeParishValue(parish) === parishKey)) {
        return false;
      }
      if (channelFilters.length > 0) {
        const platformKey = normalizeChannelValue(row.platform ?? '');
        if (!platformKey || !channelFilters.includes(platformKey)) {
          return false;
        }
      }
      return matchesQuery(row.name, query);
    });
  },
  getCreativeRowsForSelectedParish: () => {
    const { creative: creativeSlice, selectedParish, filters } = get();
    const rows = creativeSlice.data ?? [];
    const query = normalizeFilterQuery(filters.campaignQuery);
    const channelFilters = resolveChannelFilters(filters);
    if (!selectedParish) {
      return rows.filter((row) => {
        if (channelFilters.length > 0) {
          const platformKey = normalizeChannelValue(row.platform ?? '');
          if (!platformKey || !channelFilters.includes(platformKey)) {
            return false;
          }
        }
        if (!query) {
          return true;
        }
        return matchesQuery(row.campaignName, query) || matchesQuery(row.name, query);
      });
    }
    const parishKey = normalizeParishValue(selectedParish);
    return rows.filter((row) => {
      if (!row.parishes?.some((parish) => normalizeParishValue(parish) === parishKey)) {
        return false;
      }
      if (channelFilters.length > 0) {
        const platformKey = normalizeChannelValue(row.platform ?? '');
        if (!platformKey || !channelFilters.includes(platformKey)) {
          return false;
        }
      }
      if (!query) {
        return true;
      }
      return matchesQuery(row.campaignName, query) || matchesQuery(row.name, query);
    });
  },
  getBudgetRowsForSelectedParish: () => {
    const { budget: budgetSlice, selectedParish, filters } = get();
    const rows = budgetSlice.data ?? [];
    const query = normalizeFilterQuery(filters.campaignQuery);
    const channelFilters = resolveChannelFilters(filters);
    if (!selectedParish) {
      return rows.filter((row) => {
        if (channelFilters.length > 0) {
          const platformKey = normalizeChannelValue(row.platform ?? '');
          if (!platformKey || !channelFilters.includes(platformKey)) {
            return false;
          }
        }
        return matchesQuery(row.campaignName, query);
      });
    }
    const parishKey = normalizeParishValue(selectedParish);
    return rows.filter((row) => {
      if (!row.parishes?.some((parish) => normalizeParishValue(parish) === parishKey)) {
        return false;
      }
      if (channelFilters.length > 0) {
        const platformKey = normalizeChannelValue(row.platform ?? '');
        if (!platformKey || !channelFilters.includes(platformKey)) {
          return false;
        }
      }
      return matchesQuery(row.campaignName, query);
    });
  },
  reset: () => {
    resetDashboardSession();
  },
}));

let lastDashboardSessionResetVersion = getDashboardSessionState().resetVersion;

subscribeDashboardSession((sessionState) => {
  useDashboardStore.setState((state) => {
    if (sessionState.resetVersion !== lastDashboardSessionResetVersion) {
      lastDashboardSessionResetVersion = sessionState.resetVersion;
      return {
        ...createInitialState(),
      };
    }

    const nextState = applySessionStateToDashboard(state, sessionState);
    return nextState ?? state;
  });
});

export function isMockMode(): boolean {
  return MOCK_MODE;
}

export default useDashboardStore;
