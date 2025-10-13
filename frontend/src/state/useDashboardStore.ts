import { create } from "zustand";

import apiClient from "../lib/apiClient";

export type MetricRow = {
  date: string;
  platform: string;
  campaign: string;
  parish: string;
  impressions: number;
  clicks: number;
  spend: number;
  conversions: number;
  roas: number;
};

export type MetricKey = "impressions" | "clicks" | "spend" | "conversions" | "roas";

type LoadStatus = "idle" | "loading" | "loaded" | "error";

interface DashboardState {
  rows: MetricRow[];
  selectedParish?: string;
  selectedMetric: MetricKey;
  status: LoadStatus;
  error?: string;
  activeTenantId?: string;
  setSelectedParish: (parish?: string) => void;
  setSelectedMetric: (metric: MetricKey) => void;
  loadMetrics: (tenantId?: string, options?: { force?: boolean }) => Promise<void>;
  reset: () => void;
}

const initialState: Pick<DashboardState, "rows" | "selectedMetric" | "selectedParish" | "status" | "error" | "activeTenantId"> = {
  rows: [],
  selectedMetric: "impressions",
  selectedParish: undefined,
  status: "idle",
  error: undefined,
  activeTenantId: undefined,
};

const useDashboardStore = create<DashboardState>((set, get) => ({
  ...initialState,
  setSelectedParish: (parish) => {
    if (typeof parish === "undefined") {
      set({ selectedParish: undefined });
      return;
    }

    const current = get().selectedParish;
    set({ selectedParish: current === parish ? undefined : parish });
  },
  setSelectedMetric: (metric) => set({ selectedMetric: metric }),
  loadMetrics: async (tenantId, options) => {
    const { rows, status, activeTenantId } = get();
    const isSameTenant = tenantId ? tenantId === activeTenantId : true;

    if (!options?.force && status === "loaded" && rows.length > 0 && isSameTenant) {
      return;
    }

    const isTenantChange = tenantId && tenantId !== activeTenantId;

    set({
      status: "loading",
      error: undefined,
      ...(isTenantChange
        ? {
            rows: [],
            selectedParish: undefined,
          }
        : {}),
      activeTenantId: tenantId ?? activeTenantId,
    });

    try {
      const response = await apiClient.get<MetricRow[]>("/campaign-metrics/");
      set({ rows: response.data, status: "loaded", error: undefined });
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Unable to load campaign metrics. Please try again.";
      set({ rows: [], status: "error", error: message });
    }
  },
  reset: () => set({ ...initialState }),
}));

export default useDashboardStore;
