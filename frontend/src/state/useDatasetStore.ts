import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import apiClient from '../lib/apiClient';
import {
  loadDatasetStatus,
  messageForLiveDatasetReason,
  type DatasetLiveReason,
  type DatasetStatusResponse,
} from '../lib/datasetStatus';

export type DatasetMode = 'live' | 'dummy';

const STORAGE_KEY = 'dataset-mode';
const FAKE_KEY = 'fake';
const DEMO_KEY = 'demo';
const META_DIRECT_KEY = 'meta_direct';
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
  liveReason?: DatasetLiveReason;
  liveDetail?: string;
  liveSnapshotGeneratedAt?: string;
  warehouseAdapterEnabled: boolean;
  datasetStatusPayload?: DatasetStatusResponse;
  demoTenants: Array<{ id: string; label: string }>;
  demoTenantId?: string;
  setMode: (mode: DatasetMode) => void;
  toggleMode: () => DatasetMode;
  loadAdapters: () => Promise<void>;
  setDemoTenantId: (tenantId: string) => void;
}

function computeSource(
  mode: DatasetMode,
  adapters: string[],
  warehouseAdapterEnabled = adapters.includes(WAREHOUSE_KEY),
  liveReason?: DatasetLiveReason,
): string | undefined {
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
    if (warehouseAdapterEnabled && liveReason === 'ready') {
      return WAREHOUSE_KEY;
    }
    if (adapters.includes(META_DIRECT_KEY)) {
      return META_DIRECT_KEY;
    }
    if (warehouseAdapterEnabled) {
      return WAREHOUSE_KEY;
    }
    return undefined;
  }
  return undefined;
}

function hasLiveSource(
  adapters: string[],
  warehouseAdapterEnabled: boolean,
  liveReason?: DatasetLiveReason,
): boolean {
  return Boolean(computeSource('live', adapters, warehouseAdapterEnabled, liveReason));
}

export const useDatasetStore = create<DatasetState>()(
  persist(
    (set, get) => ({
      mode: 'live',
      adapters: [],
      status: 'idle',
      error: undefined,
      source: undefined,
      liveReason: undefined,
      liveDetail: undefined,
      liveSnapshotGeneratedAt: undefined,
      warehouseAdapterEnabled: false,
      datasetStatusPayload: undefined,
      demoTenants: [],
      demoTenantId: undefined,
      setMode: (mode) => {
        const { adapters, warehouseAdapterEnabled, liveReason } = get();
        const nextSource = computeSource(mode, adapters, warehouseAdapterEnabled, liveReason);
        set({
          mode,
          error:
            mode === 'live' && nextSource === WAREHOUSE_KEY && liveReason && liveReason !== 'ready'
              ? messageForLiveDatasetReason(liveReason)
              : undefined,
          source: nextSource,
        });
      },
      setDemoTenantId: (tenantId) => {
        set((s) => ({ ...s, demoTenantId: tenantId }));
      },
      toggleMode: () => {
        const { mode, adapters, warehouseAdapterEnabled, liveReason } = get();
        const next = mode === 'live' ? 'dummy' : 'live';
        const demoAvailable = adapters.includes(DEMO_KEY) || adapters.includes(FAKE_KEY);
        const liveAvailable = hasLiveSource(adapters, warehouseAdapterEnabled, liveReason);

        if (next === 'dummy' && !demoAvailable) {
          set({
            error: 'Demo dataset is unavailable.',
            source: computeSource(mode, adapters, warehouseAdapterEnabled, liveReason),
          });
          return mode;
        }

        if (next === 'live' && !liveAvailable) {
          set({
            error: messageForLiveDatasetReason(liveReason ?? 'adapter_disabled'),
            source: computeSource(mode, adapters, warehouseAdapterEnabled, liveReason),
          });
          return mode;
        }

        const nextSource = computeSource(next, adapters, warehouseAdapterEnabled, liveReason);
        set({
          mode: next,
          error:
            next === 'live' && nextSource === WAREHOUSE_KEY && liveReason && liveReason !== 'ready'
              ? messageForLiveDatasetReason(liveReason)
              : undefined,
          source: nextSource,
        });
        return next;
      },
      loadAdapters: async () => {
        if (get().status === 'loading') {
          return;
        }

        set((s) => ({ ...s, status: 'loading', error: undefined }));
        try {
          const [response, datasetStatus] = await Promise.all([
            apiClient.get<AdapterMetadata[]>('/adapters/'),
            loadDatasetStatus(),
          ]);
          const keys = response.map((adapter) => adapter.key);
          const demoMetadata = response.find((adapter) => adapter.key === DEMO_KEY);
          const demoTenants = demoMetadata?.options?.demo_tenants ?? [];

          const currentMode = get().mode;
          const liveAvailable = hasLiveSource(
            keys,
            datasetStatus.warehouse_adapter_enabled,
            datasetStatus.live.reason,
          );
          const demoAvailable = keys.includes(DEMO_KEY) || keys.includes(FAKE_KEY);

          let resolvedMode: DatasetMode = currentMode;
          if (currentMode === 'dummy') {
            if (!demoAvailable && liveAvailable) {
              resolvedMode = 'live';
            }
          } else if (currentMode === 'live') {
            resolvedMode = 'live';
          }

          const resolvedSource = computeSource(
            resolvedMode,
            keys,
            datasetStatus.warehouse_adapter_enabled,
            datasetStatus.live.reason,
          );
          const existingDemoTenantId = get().demoTenantId;
          const resolvedDemoTenantId =
            demoTenants.length === 0
              ? existingDemoTenantId
              : demoTenants.some((tenant) => tenant.id === existingDemoTenantId)
                ? existingDemoTenantId
                : demoTenants[0].id;

          const resolvedError =
            resolvedMode === 'live' && !liveAvailable
              ? messageForLiveDatasetReason(datasetStatus.live.reason)
              : resolvedMode === 'live' &&
                  resolvedSource === WAREHOUSE_KEY &&
                  datasetStatus.live.reason !== 'ready'
                ? messageForLiveDatasetReason(datasetStatus.live.reason)
              : resolvedMode === 'dummy' && !demoAvailable
                ? 'Demo dataset is unavailable.'
                : undefined;

          set((s) => ({
            ...s,
            adapters: keys,
            status: 'loaded',
            error: resolvedError,
            mode: resolvedMode,
            source: resolvedSource,
            liveReason: datasetStatus.live.reason,
            liveDetail: datasetStatus.live.detail ?? undefined,
            liveSnapshotGeneratedAt: datasetStatus.live.snapshot_generated_at ?? undefined,
            warehouseAdapterEnabled: datasetStatus.warehouse_adapter_enabled,
            datasetStatusPayload: datasetStatus,
            demoTenants,
            demoTenantId: resolvedDemoTenantId,
          }));
        } catch (error) {
          const message = error instanceof Error ? error.message : 'Unable to load datasets.';
          set((s) => ({
            ...s,
            status: 'error',
            error: message,
            source: computeSource(
              get().mode,
              get().adapters,
              get().warehouseAdapterEnabled,
              get().liveReason,
            ),
          }));
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

export function getLiveDatasetReason(): DatasetLiveReason | undefined {
  return useDatasetStore.getState().liveReason;
}

export function getLiveDatasetDetail(): string | undefined {
  return useDatasetStore.getState().liveDetail;
}

export function getDemoTenantId(): string | undefined {
  const state = useDatasetStore.getState();
  if (state.demoTenantId) {
    return state.demoTenantId;
  }
  return state.demoTenants[0]?.id;
}
