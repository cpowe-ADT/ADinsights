import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Mock } from 'vitest';

vi.mock('../lib/apiClient', () => ({
  default: {
    get: vi.fn(),
  },
}));

type AdapterMetadata = {
  key: string;
  name: string;
  description?: string | null;
  interfaces: Array<{ key: string; label: string; description?: string | null }>;
  options?: {
    demo_tenants?: Array<{ id: string; label: string }>;
  };
};

type DatasetStatusResponse = {
  live: {
    enabled: boolean;
    reason:
      | 'adapter_disabled'
      | 'missing_snapshot'
      | 'stale_snapshot'
      | 'default_snapshot'
      | 'ready';
    snapshot_generated_at?: string | null;
  };
  demo: {
    enabled: boolean;
    source?: string | null;
    tenant_count: number;
  };
  warehouse_adapter_enabled: boolean;
};

describe('useDatasetStore', () => {
  let apiGetMock: Mock;
  let useDatasetStore: typeof import('./useDatasetStore').useDatasetStore;
  let getDatasetSource: typeof import('./useDatasetStore').getDatasetSource;

  beforeEach(async () => {
    const apiModule = await import('../lib/apiClient');
    apiGetMock = apiModule.default.get as unknown as Mock;

    const storeModule = await import('./useDatasetStore');
    useDatasetStore = storeModule.useDatasetStore;
    getDatasetSource = storeModule.getDatasetSource;

    apiGetMock.mockReset();

    useDatasetStore.setState({
      mode: 'live',
      adapters: [],
      status: 'idle',
      error: undefined,
      source: undefined,
      liveReason: undefined,
      liveDetail: undefined,
      liveSnapshotGeneratedAt: undefined,
      warehouseAdapterEnabled: false,
      demoTenants: [],
      demoTenantId: undefined,
    });

    if (typeof window !== 'undefined' && window.localStorage) {
      window.localStorage.clear();
    }
  });

  const fakeAdapter: AdapterMetadata = {
    key: 'fake',
    name: 'Demo dataset',
    interfaces: [],
  };

  const warehouseAdapter: AdapterMetadata = {
    key: 'warehouse',
    name: 'Warehouse metrics',
    interfaces: [],
  };

  const metaDirectAdapter: AdapterMetadata = {
    key: 'meta_direct',
    name: 'Meta direct sync',
    interfaces: [],
  };

  const demoAdapter: AdapterMetadata = {
    key: 'demo',
    name: 'Demo tenants',
    interfaces: [],
    options: {
      demo_tenants: [
        { id: 'bank-of-jamaica', label: 'Bank of Jamaica' },
        { id: 'grace-kennedy', label: 'GraceKennedy' },
      ],
    },
  };

  const datasetStatus = (
    overrides: Partial<DatasetStatusResponse['live']> = {},
  ): DatasetStatusResponse => ({
    live: {
      enabled: true,
      reason: 'ready',
      snapshot_generated_at: '2026-04-04T10:00:00Z',
      ...overrides,
    },
    demo: {
      enabled: true,
      source: 'fake',
      tenant_count: 0,
    },
    warehouse_adapter_enabled: overrides.reason === 'adapter_disabled' ? false : true,
  });

  it('keeps live mode by default when only demo adapters are available', async () => {
    apiGetMock.mockImplementation(async (path: string) => {
      if (path === '/adapters/') {
        return [fakeAdapter];
      }
      if (path === '/datasets/status/') {
        return datasetStatus({ enabled: false, reason: 'adapter_disabled' });
      }
      throw new Error(`Unexpected path: ${path}`);
    });

    await useDatasetStore.getState().loadAdapters();

    const state = useDatasetStore.getState();
    expect(state.adapters).toEqual(['fake']);
    expect(state.mode).toBe('live');
    expect(state.source).toBeUndefined();
    expect(getDatasetSource()).toBeUndefined();
    expect(state.error).toBe('Live reporting is not enabled in this environment.');
  });

  it('uses direct Meta sync as the live source when warehouse reporting is unavailable', async () => {
    apiGetMock.mockImplementation(async (path: string) => {
      if (path === '/adapters/') {
        return [metaDirectAdapter, fakeAdapter];
      }
      if (path === '/datasets/status/') {
        return datasetStatus({ enabled: false, reason: 'adapter_disabled' });
      }
      throw new Error(`Unexpected path: ${path}`);
    });

    await useDatasetStore.getState().loadAdapters();

    const state = useDatasetStore.getState();
    expect(state.adapters).toEqual(['meta_direct', 'fake']);
    expect(state.mode).toBe('live');
    expect(state.source).toBe('meta_direct');
    expect(getDatasetSource()).toBe('meta_direct');
    expect(state.error).toBeUndefined();
  });

  it('falls back to live metrics when the demo adapter is missing', async () => {
    useDatasetStore.setState({
      mode: 'dummy',
      adapters: [],
      source: 'fake',
    });

    apiGetMock.mockImplementation(async (path: string) => {
      if (path === '/adapters/') {
        return [warehouseAdapter];
      }
      if (path === '/datasets/status/') {
        return datasetStatus();
      }
      throw new Error(`Unexpected path: ${path}`);
    });

    await useDatasetStore.getState().loadAdapters();

    const state = useDatasetStore.getState();
    expect(state.adapters).toEqual(['warehouse']);
    expect(state.mode).toBe('live');
    expect(state.source).toBe('warehouse');
    expect(state.error).toBeUndefined();
  });

  it('prevents toggling to live metrics when the warehouse adapter is unavailable', () => {
    useDatasetStore.setState({
      mode: 'dummy',
      adapters: ['fake'],
      source: 'fake',
      error: undefined,
      status: 'loaded',
      warehouseAdapterEnabled: false,
    });

    const nextMode = useDatasetStore.getState().toggleMode();

    const state = useDatasetStore.getState();
    expect(nextMode).toBe('dummy');
    expect(state.mode).toBe('dummy');
    expect(state.error).toBe('Live reporting is not enabled in this environment.');
    expect(state.source).toBe('fake');
  });

  it('toggles between live and demo metrics when both adapters are present', async () => {
    apiGetMock.mockImplementation(async (path: string) => {
      if (path === '/adapters/') {
        return [warehouseAdapter, fakeAdapter];
      }
      if (path === '/datasets/status/') {
        return datasetStatus();
      }
      throw new Error(`Unexpected path: ${path}`);
    });

    await useDatasetStore.getState().loadAdapters();

    let state = useDatasetStore.getState();
    expect(state.mode).toBe('live');
    expect(state.source).toBe('warehouse');

    const firstToggle = useDatasetStore.getState().toggleMode();
    state = useDatasetStore.getState();
    expect(firstToggle).toBe('dummy');
    expect(state.mode).toBe('dummy');
    expect(state.source).toBe('fake');
    expect(state.error).toBeUndefined();

    const secondToggle = useDatasetStore.getState().toggleMode();
    state = useDatasetStore.getState();
    expect(secondToggle).toBe('live');
    expect(state.mode).toBe('live');
    expect(state.source).toBe('warehouse');
    expect(state.error).toBeUndefined();
  });

  it('prefers the curated demo adapter when available and selects the first tenant', async () => {
    apiGetMock.mockImplementation(async (path: string) => {
      if (path === '/adapters/') {
        return [warehouseAdapter, demoAdapter];
      }
      if (path === '/datasets/status/') {
        return datasetStatus({
          enabled: true,
          reason: 'ready',
        });
      }
      throw new Error(`Unexpected path: ${path}`);
    });

    await useDatasetStore.getState().loadAdapters();

    let state = useDatasetStore.getState();
    expect(state.adapters).toEqual(['warehouse', 'demo']);
    expect(state.mode).toBe('live');
    expect(state.source).toBe('warehouse');
    expect(state.demoTenants).toHaveLength(2);
    expect(state.demoTenantId).toBe('bank-of-jamaica');

    const switched = useDatasetStore.getState().toggleMode();
    state = useDatasetStore.getState();
    expect(switched).toBe('dummy');
    expect(state.mode).toBe('dummy');
    expect(state.source).toBe('demo');
    expect(state.demoTenantId).toBe('bank-of-jamaica');

    useDatasetStore.getState().setDemoTenantId('grace-kennedy');
    state = useDatasetStore.getState();
    expect(state.demoTenantId).toBe('grace-kennedy');
  });

  it('respects the persisted demo mode when it is still available', async () => {
    useDatasetStore.setState({
      mode: 'dummy',
      adapters: [],
      source: 'fake',
    });
    apiGetMock.mockImplementation(async (path: string) => {
      if (path === '/adapters/') {
        return [warehouseAdapter, fakeAdapter];
      }
      if (path === '/datasets/status/') {
        return datasetStatus();
      }
      throw new Error(`Unexpected path: ${path}`);
    });

    await useDatasetStore.getState().loadAdapters();

    const state = useDatasetStore.getState();
    expect(state.mode).toBe('dummy');
    expect(state.source).toBe('fake');
  });

  it('stores missing snapshot state for live mode', async () => {
    apiGetMock.mockImplementation(async (path: string) => {
      if (path === '/adapters/') {
        return [warehouseAdapter, fakeAdapter];
      }
      if (path === '/datasets/status/') {
        return datasetStatus({
          enabled: false,
          reason: 'missing_snapshot',
          snapshot_generated_at: null,
        });
      }
      throw new Error(`Unexpected path: ${path}`);
    });

    await useDatasetStore.getState().loadAdapters();

    const state = useDatasetStore.getState();
    expect(state.mode).toBe('live');
    expect(state.liveReason).toBe('missing_snapshot');
    expect(state.error).toBe(
      'Meta is connected, but the first live warehouse snapshot has not been generated yet.',
    );
  });
});
