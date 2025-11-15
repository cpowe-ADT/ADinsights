import { create } from 'zustand';

import { MOCK_MODE } from '../lib/apiClient';
import { clearView, loadSavedView, saveView } from '../lib/savedViews';
import {
  fetchBudgetPacing,
  fetchCampaignPerformance,
  fetchCreativePerformance,
  fetchParishAggregates,
  fetchDashboardMetrics,
} from '../lib/dataService';
import { validate } from '../lib/validate';
import type { SchemaKey } from '../lib/validate';
import { getDatasetMode, getDatasetSource, getDemoTenantId } from './useDatasetStore';

export type MetricKey = 'spend' | 'impressions' | 'clicks' | 'conversions' | 'roas';

export type LoadStatus = 'idle' | 'loading' | 'loaded' | 'error';

export interface CampaignPerformanceSummary {
  currency: string;
  totalSpend: number;
  totalImpressions: number;
  totalClicks: number;
  totalConversions: number;
  averageRoas: number;
}

export interface CampaignTrendPoint {
  date: string;
  spend: number;
  conversions: number;
  clicks: number;
  impressions: number;
}

export interface CampaignPerformanceRow {
  id: string;
  name: string;
  platform: string;
  status: string;
  objective?: string;
  parish?: string;
  spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  roas: number;
  ctr?: number;
  cpc?: number;
  cpm?: number;
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
  name: string;
  campaignId: string;
  campaignName: string;
  platform: string;
  parish?: string;
  spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  roas: number;
  ctr?: number;
  thumbnailUrl?: string;
}

export interface BudgetPacingRow {
  id: string;
  campaignName: string;
  parishes?: string[];
  monthlyBudget: number;
  spendToDate: number;
  projectedSpend: number;
  pacingPercent: number;
  startDate?: string;
  endDate?: string;
}

export interface ParishAggregate {
  parish: string;
  spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  roas?: number;
  campaignCount?: number;
  currency?: string;
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
  [key: string]: unknown;
}

export interface TenantMetricsResolved {
  campaign: CampaignPerformanceResponse;
  creative: CreativePerformanceRow[];
  budget: BudgetPacingRow[];
  parish: ParishAggregate[];
  tenantId?: string;
  currency: string;
  snapshotGeneratedAt?: string;
}

type AsyncSlice<T> = {
  status: LoadStatus;
  data?: T;
  error?: string;
};

interface DashboardState {
  selectedParish?: string;
  selectedMetric: MetricKey;
  campaign: AsyncSlice<CampaignPerformanceResponse>;
  creative: AsyncSlice<CreativePerformanceRow[]>;
  budget: AsyncSlice<BudgetPacingRow[]>;
  parish: AsyncSlice<ParishAggregate[]>;
  activeTenantId?: string;
  activeTenantLabel?: string;
  lastLoadedTenantId?: string;
  lastSnapshotGeneratedAt?: string;
  metricsCache: Record<string, TenantMetricsResolved>;
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
}

const initialSlice = <T>(): AsyncSlice<T> => ({
  status: 'idle',
  data: undefined,
  error: undefined,
});

const DEFAULT_TENANT_KEY = '__default__';

function createInitialState(): Pick<
  DashboardState,
  | 'selectedParish'
  | 'selectedMetric'
  | 'campaign'
  | 'creative'
  | 'budget'
  | 'parish'
  | 'activeTenantId'
  | 'activeTenantLabel'
  | 'lastLoadedTenantId'
  | 'lastSnapshotGeneratedAt'
  | 'metricsCache'
> {
  return {
    selectedParish: undefined,
    selectedMetric: 'spend',
    campaign: initialSlice(),
    creative: initialSlice(),
    budget: initialSlice(),
    parish: initialSlice(),
    activeTenantId: undefined,
    activeTenantLabel: undefined,
    lastLoadedTenantId: undefined,
    lastSnapshotGeneratedAt: undefined,
    metricsCache: {},
  };
}

function resolveTenantKey(tenantId?: string): string {
  const datasetKey = getDatasetMode();
  return `${tenantId ?? DEFAULT_TENANT_KEY}::${datasetKey}`;
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
  tenantId?: string;
  snapshotGeneratedAt?: string;
}): TenantMetricsResolved {
  const campaign = normalizeCampaignResponse(input.campaign);
  const parish = normalizeParishAggregates(input.parish, campaign.summary.currency);
  const currency = campaign.summary.currency;

  return {
    campaign,
    creative: input.creative,
    budget: input.budget,
    parish,
    tenantId: input.tenantId,
    currency,
    snapshotGeneratedAt: input.snapshotGeneratedAt,
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
  });
}

function withTenant(path: string, tenantId?: string): string {
  if (!tenantId) {
    return path;
  }
  const separator = path.includes('?') ? '&' : '?';
  return `${path}${separator}tenant_id=${encodeURIComponent(tenantId)}`;
}

function withSource(path: string, source?: string | undefined): string {
  if (!source) {
    return path;
  }
  const separator = path.includes('?') ? '&' : '?';
  return `${path}${separator}source=${encodeURIComponent(source)}`;
}

function withQueryParam(path: string, key: string, value?: string): string {
  if (!value) {
    return path;
  }
  const separator = path.includes('?') ? '&' : '?';
  return `${path}${separator}${encodeURIComponent(key)}=${encodeURIComponent(value)}`;
}

function mapError(reason: unknown): string {
  if (reason instanceof Error) {
    return reason.message;
  }
  return 'Unable to load the latest insights. Please try again.';
}

async function fetchDummySnapshot(path = '/sample_metrics.json'): Promise<TenantMetricsSnapshot> {
  const response = await fetch(path, { credentials: 'same-origin' });
  if (!response.ok) {
    throw new Error('Unable to load demo metrics snapshot.');
  }
  return (await response.json()) as TenantMetricsSnapshot;
}

const useDashboardStore = create<DashboardState>((set, get) => ({
  ...createInitialState(),
  getSavedTableView: (tableId) => loadSavedView(tableId),
  setSavedTableView: (tableId, view) => saveView(tableId, view),
  clearSavedTableView: (tableId) => clearView(tableId),
  setSelectedParish: (parish) => {
    if (!parish) {
      set({ selectedParish: undefined });
      return;
    }
    const current = get().selectedParish;
    set({ selectedParish: current === parish ? undefined : parish });
  },
  setSelectedMetric: (metric) => set({ selectedMetric: metric }),
  setActiveTenant: (tenantId, tenantLabel) => {
    const normalizedTenantId = normalizeTenantId(tenantId);
    const normalizedLabel =
      typeof tenantLabel === 'string' && tenantLabel.trim() ? tenantLabel.trim() : undefined;

    set((state) => {
      const currentTenantId = normalizeTenantId(state.activeTenantId);
      const hasChanged = normalizedTenantId !== currentTenantId;

      return {
        activeTenantId: normalizedTenantId,
        activeTenantLabel: normalizedLabel ?? (hasChanged ? undefined : state.activeTenantLabel),
        selectedParish: hasChanged ? undefined : state.selectedParish,
      };
    });
  },
  loadAll: async (tenantId, options) => {
    const {
      campaign,
      creative,
      budget,
      parish,
      activeTenantId,
      lastLoadedTenantId,
      metricsCache,
    } = get();
    const requestedTenantId =
      typeof tenantId === 'undefined' ? activeTenantId : tenantId ?? activeTenantId;
    const normalizedTenantId = normalizeTenantId(requestedTenantId);
    const tenantKey = resolveTenantKey(normalizedTenantId);
    const cachedMetrics = metricsCache[tenantKey];
    const normalizedLastLoaded = normalizeTenantId(lastLoadedTenantId);
    const isTenantChange =
      typeof normalizedTenantId !== 'undefined' && normalizedTenantId !== normalizedLastLoaded;
    const allSlicesLoaded =
      campaign.status === 'loaded' &&
      creative.status === 'loaded' &&
      budget.status === 'loaded' &&
      parish.status === 'loaded';

    if (!options?.force) {
      if (!isTenantChange && allSlicesLoaded) {
        return;
      }

      if (cachedMetrics && isTenantChange) {
        set((state) => ({
          activeTenantId: cachedMetrics.tenantId ?? normalizedTenantId ?? state.activeTenantId,
          lastLoadedTenantId: cachedMetrics.tenantId ?? normalizedTenantId ?? state.lastLoadedTenantId,
          lastSnapshotGeneratedAt:
            cachedMetrics.snapshotGeneratedAt ?? state.lastSnapshotGeneratedAt,
          selectedParish: undefined,
          campaign: { status: 'loaded', data: cachedMetrics.campaign, error: undefined },
          creative: { status: 'loaded', data: cachedMetrics.creative, error: undefined },
          budget: { status: 'loaded', data: cachedMetrics.budget, error: undefined },
          parish: { status: 'loaded', data: cachedMetrics.parish, error: undefined },
        }));
        return;
      }

      if (cachedMetrics && !isTenantChange && !allSlicesLoaded) {
        set((state) => ({
          activeTenantId: cachedMetrics.tenantId ?? state.activeTenantId,
          lastLoadedTenantId: cachedMetrics.tenantId ?? state.lastLoadedTenantId,
          lastSnapshotGeneratedAt:
            cachedMetrics.snapshotGeneratedAt ?? state.lastSnapshotGeneratedAt,
          campaign: { status: 'loaded', data: cachedMetrics.campaign, error: undefined },
          creative: { status: 'loaded', data: cachedMetrics.creative, error: undefined },
          budget: { status: 'loaded', data: cachedMetrics.budget, error: undefined },
          parish: { status: 'loaded', data: cachedMetrics.parish, error: undefined },
        }));
        return;
      }
    }

    set((state) => ({
      activeTenantId: normalizedTenantId ?? state.activeTenantId,
      lastLoadedTenantId: state.lastLoadedTenantId,
      selectedParish: isTenantChange ? undefined : state.selectedParish,
      campaign: { ...state.campaign, status: 'loading', error: undefined },
      creative: { ...state.creative, status: 'loading', error: undefined },
      budget: { ...state.budget, status: 'loading', error: undefined },
      parish: { ...state.parish, status: 'loading', error: undefined },
    }));

    const datasetMode = getDatasetMode();
    const sourceOverride = getDatasetSource();
    const metricsSource = sourceOverride;
    let metricsPath = withSource(
      withTenant('/metrics/combined/', normalizedTenantId),
      sourceOverride,
    );
    if (metricsSource === 'demo') {
      metricsPath = withQueryParam(metricsPath, 'demo_tenant', getDemoTenantId());
    }

    if (!MOCK_MODE && datasetMode !== 'dummy') {
      try {
        const snapshot = await fetchDashboardMetrics({
          path: metricsPath,
          mockPath: '/sample_metrics.json',
        });
        const resolved = parseTenantMetrics(snapshot);

        set((state) => ({
          activeTenantId: resolved.tenantId ?? state.activeTenantId,
          lastLoadedTenantId: resolved.tenantId ?? normalizedTenantId ?? state.lastLoadedTenantId,
          lastSnapshotGeneratedAt:
            resolved.snapshotGeneratedAt ?? state.lastSnapshotGeneratedAt,
          campaign: { status: 'loaded', data: resolved.campaign, error: undefined },
          creative: { status: 'loaded', data: resolved.creative, error: undefined },
          budget: { status: 'loaded', data: resolved.budget, error: undefined },
          parish: { status: 'loaded', data: resolved.parish, error: undefined },
          metricsCache: { ...state.metricsCache, [tenantKey]: resolved },
        }));
      } catch (error) {
        const message = mapError(error);
        set((state) => ({
          campaign: { status: 'error', data: state.campaign.data, error: message },
          creative: { status: 'error', data: state.creative.data, error: message },
          budget: { status: 'error', data: state.budget.data, error: message },
          parish: { status: 'error', data: state.parish.data, error: message },
        }));
      }

      return;
    }

    if (datasetMode === 'dummy') {
      try {
        let dummyPath = '/sample_metrics.json';
        if (metricsSource) {
          dummyPath = withSource(dummyPath, metricsSource);
        }
        if (metricsSource === 'demo') {
          dummyPath = withQueryParam(dummyPath, 'demo_tenant', getDemoTenantId());
        }

        const snapshot = await fetchDummySnapshot(dummyPath);
        const resolved = parseTenantMetrics(snapshot);

        set((state) => ({
          activeTenantId: resolved.tenantId ?? state.activeTenantId,
          lastLoadedTenantId: resolved.tenantId ?? normalizedTenantId ?? state.lastLoadedTenantId,
          lastSnapshotGeneratedAt:
            resolved.snapshotGeneratedAt ?? state.lastSnapshotGeneratedAt,
          campaign: { status: 'loaded', data: resolved.campaign, error: undefined },
          creative: { status: 'loaded', data: resolved.creative, error: undefined },
          budget: { status: 'loaded', data: resolved.budget, error: undefined },
          parish: { status: 'loaded', data: resolved.parish, error: undefined },
          metricsCache: { ...state.metricsCache, [tenantKey]: resolved },
        }));
      } catch (error) {
        const message = mapError(error);
        set((state) => ({
          campaign: { status: 'error', data: state.campaign.data, error: message },
          creative: { status: 'error', data: state.creative.data, error: message },
          budget: { status: 'error', data: state.budget.data, error: message },
          parish: { status: 'error', data: state.parish.data, error: message },
        }));
      }

      return;
    }

    const campaignPath = withSource(
      withTenant('/analytics/campaign-performance/', tenantId),
      sourceOverride,
    );
    const creativePath = withSource(
      withTenant('/analytics/creative-performance/', tenantId),
      sourceOverride,
    );
    const budgetPath = withSource(
      withTenant('/analytics/budget-pacing/', tenantId),
      sourceOverride,
    );
    const parishPath = withSource(
      withTenant('/analytics/parish-performance/', tenantId),
      sourceOverride,
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
        lastLoadedTenantId: normalizedResolved?.tenantId ?? normalizedTenantId ?? state.lastLoadedTenantId,
        lastSnapshotGeneratedAt:
          normalizedResolved?.snapshotGeneratedAt ?? state.lastSnapshotGeneratedAt,
        campaign:
          campaignResult.status === 'fulfilled'
            ? { status: 'loaded', data: normalizedCampaign!, error: undefined }
            : {
                status: 'error',
                data: state.campaign.data,
                error: mapError(campaignResult.reason),
              },
        creative:
          creativeResult.status === 'fulfilled'
            ? { status: 'loaded', data: normalizedCreative!, error: undefined }
            : {
                status: 'error',
                data: state.creative.data,
                error: mapError(creativeResult.reason),
              },
        budget:
          budgetResult.status === 'fulfilled'
            ? { status: 'loaded', data: normalizedBudget!, error: undefined }
            : {
                status: 'error',
                data: state.budget.data,
                error: mapError(budgetResult.reason),
              },
        parish: normalizedParish
          ? { status: 'loaded', data: normalizedParish, error: undefined }
          : {
              status: 'error',
              data: state.parish.data,
              error: mapError(parishErrorReason),
            },
        metricsCache: updatedCache,
      };
    });
  },
  getCachedMetrics: (tenantId) => {
    const state = get();
    const normalizedTenantId = normalizeTenantId(tenantId ?? state.activeTenantId);
    const tenantKey = resolveTenantKey(normalizedTenantId);
    return state.metricsCache[tenantKey];
  },
  getCampaignRowsForSelectedParish: () => {
    const { campaign: campaignSlice, selectedParish } = get();
    const rows = campaignSlice.data?.rows ?? [];
    if (!selectedParish) {
      return rows;
    }
    return rows.filter((row) => row.parish?.toLowerCase() === selectedParish.toLowerCase());
  },
  getCreativeRowsForSelectedParish: () => {
    const { creative: creativeSlice, selectedParish } = get();
    const rows = creativeSlice.data ?? [];
    if (!selectedParish) {
      return rows;
    }
    return rows.filter((row) => row.parish?.toLowerCase() === selectedParish.toLowerCase());
  },
  getBudgetRowsForSelectedParish: () => {
    const { budget: budgetSlice, selectedParish } = get();
    const rows = budgetSlice.data ?? [];
    if (!selectedParish) {
      return rows;
    }
    return rows.filter((row) =>
      row.parishes?.some((parish) => parish.toLowerCase() === selectedParish.toLowerCase()),
    );
  },
  reset: () => {
    set({
      ...createInitialState(),
    });
  },
}));

export function isMockMode(): boolean {
  return MOCK_MODE;
}

export default useDashboardStore;
