import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import apiClient from '../lib/apiClient';

export type DatasetMode = 'live' | 'dummy';

const STORAGE_KEY = 'dataset-mode';
const FAKE_KEY = 'fake';
const DEMO_KEY = 'demo';
const WAREHOUSE_KEY = 'warehouse';

interface AdapterMetadata {
  key: string;
  name: string;
  description?: string | null;
  interfaces: Array<{ key: string; label: string; description?: string | null }>;
  options?: {
    demo_tenants?: Array<{ id: string; label: string }>;
  };
}

type LoadStatus = 'idle' | 'loading' | 'loaded' | 'error';

interface DatasetState {
  mode: DatasetMode;
  adapters: string[];
  status: LoadStatus;
  error?: string;
  source?: string;
  demoTenants: Array<{ id: string; label: string }>;
  demoTenantId?: string;
  setMode: (mode: DatasetMode) => void;
  toggleMode: () => DatasetMode;
  loadAdapters: () => Promise<void>;
  setDemoTenantId: (tenantId: string) => void;
}

function computeSource(mode: DatasetMode, adapters: string[]): string | undefined {
  if (mode === 'dummy') {
    if (adapters.includes(DEMO_KEY)) {
      return DEMO_KEY;
    }
    if (adapters.includes(FAKE_KEY)) {
      return FAKE_KEY;
    }
    return undefined;
  }
  if (mode === 'live') {
    return adapters.includes(WAREHOUSE_KEY) ? WAREHOUSE_KEY : undefined;
  }
  return undefined;
}

export const useDatasetStore = create<DatasetState>()(
  persist(
    (set, get) => ({
      mode: 'live',
      adapters: [],
      status: 'idle',
      error: undefined,
      source: undefined,
      demoTenants: [],
      demoTenantId: undefined,
      setMode: (mode) => {
        const { adapters } = get();
        set({
          mode,
          error: undefined,
          source: computeSource(mode, adapters),
        });
      },
      setDemoTenantId: (tenantId) => {
        set({ demoTenantId: tenantId });
      },
      toggleMode: () => {
        const { mode, adapters } = get();
        const next = mode === 'live' ? 'dummy' : 'live';
        const demoAvailable = adapters.includes(DEMO_KEY) || adapters.includes(FAKE_KEY);
        const liveAvailable = adapters.includes(WAREHOUSE_KEY);

        if (next === 'dummy' && !demoAvailable) {
          set({
            error: 'Demo dataset is unavailable.',
            source: computeSource(mode, adapters),
          });
          return mode;
        }

        if (next === 'live' && !liveAvailable) {
          set({
            error: 'Live warehouse metrics are unavailable.',
            source: computeSource(mode, adapters),
          });
          return mode;
        }

        set({ mode: next, error: undefined, source: computeSource(next, adapters) });
        return next;
      },
      loadAdapters: async () => {
        if (get().status === 'loading') {
          return;
        }

        set({ status: 'loading', error: undefined });
        try {
          const response = await apiClient.get<AdapterMetadata[]>('/adapters/');
          const keys = response.map((adapter) => adapter.key);
          const demoMetadata = response.find((adapter) => adapter.key === DEMO_KEY);
          const demoTenants = demoMetadata?.options?.demo_tenants ?? [];

          const currentMode = get().mode;
          let resolvedMode = currentMode;
          if (currentMode === 'dummy' && !(keys.includes(DEMO_KEY) || keys.includes(FAKE_KEY))) {
            resolvedMode = 'live';
          } else if (
            currentMode === 'live' &&
            !keys.includes(WAREHOUSE_KEY) &&
            (keys.includes(DEMO_KEY) || keys.includes(FAKE_KEY))
          ) {
            resolvedMode = 'dummy';
          }

          const resolvedSource = computeSource(resolvedMode, keys);
          const existingDemoTenantId = get().demoTenantId;
          const resolvedDemoTenantId =
            demoTenants.length === 0
              ? existingDemoTenantId
              : demoTenants.some((tenant) => tenant.id === existingDemoTenantId)
              ? existingDemoTenantId
              : demoTenants[0].id;

          set({
            adapters: keys,
            status: 'loaded',
            error: undefined,
            mode: resolvedMode,
            source: resolvedSource,
            demoTenants,
            demoTenantId: resolvedDemoTenantId,
          });
        } catch (error) {
          const message = error instanceof Error ? error.message : 'Unable to load datasets.';
          set({
            status: 'error',
            error: message,
            source: computeSource(get().mode, get().adapters),
          });
        }
      },
    }),
    {
      name: STORAGE_KEY,
      partialize: (state) => ({ mode: state.mode, demoTenantId: state.demoTenantId }),
    },
  ),
);

export function getDatasetMode(): DatasetMode {
  return useDatasetStore.getState().mode;
}

export function getDatasetSource(): string | undefined {
  return useDatasetStore.getState().source;
}

export function getDemoTenantId(): string | undefined {
  const state = useDatasetStore.getState();
  if (state.demoTenantId) {
    return state.demoTenantId;
  }
  return state.demoTenants[0]?.id;
}
