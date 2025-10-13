import { create } from "zustand";

import { MOCK_MODE } from "../lib/apiClient";
import { clearView, loadSavedView, saveView } from "../lib/savedViews";
import {
  fetchBudgetPacing,
  fetchCampaignPerformance,
  fetchCreativePerformance,
  fetchParishAggregates,
  fetchDashboardMetrics,
} from "../lib/dataService";

export type MetricKey = "spend" | "impressions" | "clicks" | "conversions" | "roas";

export type LoadStatus = "idle" | "loading" | "loaded" | "error";

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
  [key: string]: unknown;
}

export interface TenantMetricsResolved {
  campaign: CampaignPerformanceResponse;
  creative: CreativePerformanceRow[];
  budget: BudgetPacingRow[];
  parish: ParishAggregate[];
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
  metricsCache: Record<string, TenantMetricsResolved>;
  setSelectedParish: (parish?: string) => void;
  setSelectedMetric: (metric: MetricKey) => void;
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

const initialSlice = <T,>(): AsyncSlice<T> => ({ status: "idle", data: undefined, error: undefined });

const DEFAULT_TENANT_KEY = "__default__";

function createInitialState(): Pick<
  DashboardState,
  | "selectedParish"
  | "selectedMetric"
  | "campaign"
  | "creative"
  | "budget"
  | "parish"
  | "activeTenantId"
  | "metricsCache"
> {
  return {
    selectedParish: undefined,
    selectedMetric: "spend",
    campaign: initialSlice(),
    creative: initialSlice(),
    budget: initialSlice(),
    parish: initialSlice(),
    activeTenantId: undefined,
    metricsCache: {},
  };
}

function resolveTenantKey(tenantId?: string): string {
  return tenantId ?? DEFAULT_TENANT_KEY;
}

function parseTenantMetrics(snapshot: TenantMetricsSnapshot): TenantMetricsResolved {
  const campaign =
    snapshot.campaign ?? snapshot.campaigns ?? snapshot.campaign_performance;

  if (!campaign) {
    throw new Error("Campaign metrics missing from aggregated response");
  }

  const creative = snapshot.creative ?? snapshot.creatives ?? snapshot.creative_performance ?? [];
  const budget = snapshot.budget ?? snapshot.budgets ?? snapshot.budget_pacing ?? [];
  const parish = snapshot.parish ?? snapshot.parishes ?? snapshot.parish_aggregates ?? [];

  return {
    campaign,
    creative,
    budget,
    parish,
  };
}

function withTenant(path: string, tenantId?: string): string {
  if (!tenantId) {
    return path;
  }
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}tenant_id=${encodeURIComponent(tenantId)}`;
}

function mapError(reason: unknown): string {
  if (reason instanceof Error) {
    return reason.message;
  }
  return "Unable to load the latest insights. Please try again.";
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
  loadAll: async (tenantId, options) => {
    const { campaign, creative, budget, parish, activeTenantId, metricsCache } = get();
    const tenantKey = resolveTenantKey(tenantId);
    const cachedMetrics = metricsCache[tenantKey];
    const isTenantChange = Boolean(tenantId && tenantId !== activeTenantId);
    const allSlicesLoaded =
      campaign.status === "loaded" && creative.status === "loaded" && budget.status === "loaded" && parish.status === "loaded";

    if (!options?.force) {
      if (!isTenantChange && allSlicesLoaded) {
        return;
      }

      if (cachedMetrics && isTenantChange) {
        set((state) => ({
          activeTenantId: tenantId ?? state.activeTenantId,
          selectedParish: undefined,
          campaign: { status: "loaded", data: cachedMetrics.campaign, error: undefined },
          creative: { status: "loaded", data: cachedMetrics.creative, error: undefined },
          budget: { status: "loaded", data: cachedMetrics.budget, error: undefined },
          parish: { status: "loaded", data: cachedMetrics.parish, error: undefined },
        }));
        return;
      }

      if (cachedMetrics && !isTenantChange && !allSlicesLoaded) {
        set((state) => ({
          campaign: { status: "loaded", data: cachedMetrics.campaign, error: undefined },
          creative: { status: "loaded", data: cachedMetrics.creative, error: undefined },
          budget: { status: "loaded", data: cachedMetrics.budget, error: undefined },
          parish: { status: "loaded", data: cachedMetrics.parish, error: undefined },
        }));
        return;
      }
    }

    set((state) => ({
      activeTenantId: tenantId ?? state.activeTenantId,
      selectedParish: isTenantChange ? undefined : state.selectedParish,
      campaign: { ...state.campaign, status: "loading", error: undefined },
      creative: { ...state.creative, status: "loading", error: undefined },
      budget: { ...state.budget, status: "loading", error: undefined },
      parish: { ...state.parish, status: "loading", error: undefined },
    }));

    if (!MOCK_MODE) {
      const metricsPath = withTenant("/metrics/", tenantId);

      try {
        const snapshot = await fetchDashboardMetrics({
          path: metricsPath,
          mockPath: "/sample_metrics.json",
        });
        const resolved = parseTenantMetrics(snapshot);

        set((state) => ({
          campaign: { status: "loaded", data: resolved.campaign, error: undefined },
          creative: { status: "loaded", data: resolved.creative, error: undefined },
          budget: { status: "loaded", data: resolved.budget, error: undefined },
          parish: { status: "loaded", data: resolved.parish, error: undefined },
          metricsCache: { ...state.metricsCache, [tenantKey]: resolved },
        }));
      } catch (error) {
        const message = mapError(error);
        set((state) => ({
          campaign: { status: "error", data: state.campaign.data, error: message },
          creative: { status: "error", data: state.creative.data, error: message },
          budget: { status: "error", data: state.budget.data, error: message },
          parish: { status: "error", data: state.parish.data, error: message },
        }));
      }

      return;
    }

    const campaignPath = withTenant("/dashboards/campaign-performance/", tenantId);
    const creativePath = withTenant("/dashboards/creative-performance/", tenantId);
    const budgetPath = withTenant("/dashboards/budget-pacing/", tenantId);
    const parishPath = withTenant("/dashboards/parish-performance/", tenantId);

    const [campaignResult, creativeResult, budgetResult, parishResult] = await Promise.allSettled([
      fetchCampaignPerformance({
        path: campaignPath,
        mockPath: "/sample_campaign_performance.json",
      }),
      fetchCreativePerformance({
        path: creativePath,
        mockPath: "/sample_creative_performance.json",
      }),
      fetchBudgetPacing({
        path: budgetPath,
        mockPath: "/sample_budget_pacing.json",
      }),
      fetchParishAggregates({
        path: parishPath,
        mockPath: "/sample_parish_aggregates.json",
      }),
    ]);

    set((state) => {
      const fulfilled =
        campaignResult.status === "fulfilled" &&
        creativeResult.status === "fulfilled" &&
        budgetResult.status === "fulfilled" &&
        parishResult.status === "fulfilled";

      const updatedCache = fulfilled
        ? {
            ...state.metricsCache,
            [tenantKey]: {
              campaign: campaignResult.value,
              creative: creativeResult.value,
              budget: budgetResult.value,
              parish: parishResult.value,
            },
          }
        : state.metricsCache;

      return {
        campaign:
          campaignResult.status === "fulfilled"
            ? { status: "loaded", data: campaignResult.value, error: undefined }
            : {
                status: "error",
                data: state.campaign.data,
                error: mapError(campaignResult.reason),
              },
        creative:
          creativeResult.status === "fulfilled"
            ? { status: "loaded", data: creativeResult.value, error: undefined }
            : {
                status: "error",
                data: state.creative.data,
                error: mapError(creativeResult.reason),
              },
        budget:
          budgetResult.status === "fulfilled"
            ? { status: "loaded", data: budgetResult.value, error: undefined }
            : {
                status: "error",
                data: state.budget.data,
                error: mapError(budgetResult.reason),
              },
        parish:
          parishResult.status === "fulfilled"
            ? { status: "loaded", data: parishResult.value, error: undefined }
            : {
                status: "error",
                data: state.parish.data,
                error: mapError(parishResult.reason),
              },
        metricsCache: updatedCache,
      };
    });
  },
  getCachedMetrics: (tenantId) => {
    const state = get();
    const tenantKey = resolveTenantKey(tenantId ?? state.activeTenantId);
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
    return rows.filter((row) => row.parishes?.some((parish) => parish.toLowerCase() === selectedParish.toLowerCase()));
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
