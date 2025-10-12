import { create } from "zustand";
import axios from "axios";

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

interface DashboardState {
  rows: MetricRow[];
  selectedParish?: string;
  selectedMetric: MetricKey;
  setSelectedParish: (parish?: string) => void;
  setSelectedMetric: (metric: MetricKey) => void;
  loadSampleData: () => Promise<void>;
}

const useDashboardStore = create<DashboardState>((set) => ({
  rows: [],
  selectedMetric: "impressions",
  setSelectedParish: (parish) => set({ selectedParish: parish }),
  setSelectedMetric: (metric) => set({ selectedMetric: metric }),
  loadSampleData: async () => {
    const response = await axios.get<MetricRow[]>("/sample_metrics.json");
    set({ rows: response.data });
  },
}));

export default useDashboardStore;
