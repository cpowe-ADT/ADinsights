import { create } from "zustand";

import { MOCK_MODE } from "../lib/apiClient";
import {
  fetchBudgetPacing,
  fetchCampaignPerformance,
  fetchCreativePerformance,
  fetchMetrics,
  fetchParishAggregates,
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
  setSelectedParish: (parish?: string) => void;
  setSelectedMetric: (metric: MetricKey) => void;
  loadAll: (tenantId?: string, options?: { force?: boolean }) => Promise<void>;
  reset: () => void;
}

const initialSlice = <T,>(): AsyncSlice<T> => ({ status: "idle", data: undefined, error: undefined });

const initialState: Pick<
  DashboardState,
  | "selectedParish"
  | "selectedMetric"
  | "campaign"
  | "creative"
  | "budget"
  | "parish"
  | "activeTenantId"
> = {
  selectedParish: undefined,
  selectedMetric: "spend",
  campaign: initialSlice(),
  creative: initialSlice(),
  budget: initialSlice(),
  parish: initialSlice(),
  activeTenantId: undefined,
};

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
  ...initialState,
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
    const { campaign, creative, budget, parish, activeTenantId } = get();
    const isTenantChange = tenantId && tenantId !== activeTenantId;
    const alreadyLoaded =
      !isTenantChange &&
      campaign.status === "loaded" &&
      creative.status === "loaded" &&
      budget.status === "loaded" &&
      parish.status === "loaded";

    if (!options?.force && alreadyLoaded) {
      return;
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
        const metrics = await fetchMetrics(metricsPath);
        set({
          campaign: { status: "loaded", data: metrics.campaign, error: undefined },
          creative: { status: "loaded", data: metrics.creative, error: undefined },
          budget: { status: "loaded", data: metrics.budget, error: undefined },
          parish: { status: "loaded", data: metrics.parish, error: undefined },
        });
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

    set((state) => ({
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
    }));
  },
  reset: () => {
    set({
      ...initialState,
    });
  },
}));

export function isMockMode(): boolean {
  return MOCK_MODE;
}

export default useDashboardStore;
