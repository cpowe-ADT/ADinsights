import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import apiClient from '../lib/apiClient';

export type DatasetMode = 'live' | 'dummy';

const STORAGE_KEY = 'dataset-mode';
const FAKE_KEY = 'fake';
const WAREHOUSE_KEY = 'warehouse';

interface AdapterMetadata {
  key: string;
  name: string;
  description?: string | null;
  interfaces: Array<{ key: string; label: string; description?: string | null }>;
}

type LoadStatus = 'idle' | 'loading' | 'loaded' | 'error';

interface DatasetState {
  mode: DatasetMode;
  adapters: string[];
  status: LoadStatus;
  error?: string;
  source?: string;
  setMode: (mode: DatasetMode) => void;
  toggleMode: () => DatasetMode;
  loadAdapters: () => Promise<void>;
}

function computeSource(mode: DatasetMode, adapters: string[]): string | undefined {
  if (mode === 'dummy') {
    return adapters.includes(FAKE_KEY) ? FAKE_KEY : undefined;
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
      setMode: (mode) => {
        const { adapters } = get();
        set({ mode, error: undefined, source: computeSource(mode, adapters) });
      },
      toggleMode: () => {
        const { mode, adapters } = get();
        const next = mode === 'live' ? 'dummy' : 'live';

        if (next === 'dummy' && !adapters.includes(FAKE_KEY)) {
          set({ error: 'Demo dataset is unavailable.', source: computeSource(mode, adapters) });
          return mode;
        }

        if (next === 'live' && !adapters.includes(WAREHOUSE_KEY)) {
          set({ error: 'Live warehouse metrics are unavailable.', source: computeSource(mode, adapters) });
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
          const currentMode = get().mode;
          let resolvedMode = currentMode;

          if (currentMode === 'dummy' && !keys.includes(FAKE_KEY)) {
            resolvedMode = 'live';
          } else if (currentMode === 'live' && !keys.includes(WAREHOUSE_KEY) && keys.includes(FAKE_KEY)) {
            resolvedMode = 'dummy';
          }

          set({
            adapters: keys,
            status: 'loaded',
            error: undefined,
            mode: resolvedMode,
            source: computeSource(resolvedMode, keys),
          });
        } catch (error) {
          const message = error instanceof Error ? error.message : 'Unable to load datasets.';
          set({ status: 'error', error: message, source: computeSource(get().mode, get().adapters) });
        }
      },
    }),
    {
      name: STORAGE_KEY,
      partialize: (state) => ({ mode: state.mode }),
    },
  ),
);

export function getDatasetMode(): DatasetMode {
  return useDatasetStore.getState().mode;
}

export function getDatasetSource(): string | undefined {
  return useDatasetStore.getState().source;
}
