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

describe('useDatasetStore', () => {
  let apiGetMock: Mock<[string], Promise<AdapterMetadata[]>>;
  let useDatasetStore: typeof import('./useDatasetStore').useDatasetStore;
  let getDatasetSource: typeof import('./useDatasetStore').getDatasetSource;

  beforeEach(async () => {
    const apiModule = await import('../lib/apiClient');
    apiGetMock = apiModule.default.get as unknown as Mock<[string], Promise<AdapterMetadata[]>>;

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

  it('switches to the demo dataset when only the fake adapter is available', async () => {
    apiGetMock.mockResolvedValueOnce([fakeAdapter]);

    await useDatasetStore.getState().loadAdapters();

    const state = useDatasetStore.getState();
    expect(state.adapters).toEqual(['fake']);
    expect(state.mode).toBe('dummy');
    expect(state.source).toBe('fake');
    expect(getDatasetSource()).toBe('fake');
    expect(state.error).toBeUndefined();
  });

  it('falls back to live metrics when the demo adapter is missing', async () => {
    useDatasetStore.setState({
      mode: 'dummy',
      adapters: [],
      source: 'fake',
    });

    apiGetMock.mockResolvedValueOnce([warehouseAdapter]);

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
    });

    const nextMode = useDatasetStore.getState().toggleMode();

    const state = useDatasetStore.getState();
    expect(nextMode).toBe('dummy');
    expect(state.mode).toBe('dummy');
    expect(state.error).toBe('Live warehouse metrics are unavailable.');
    expect(state.source).toBe('fake');
  });

  it('toggles between live and demo metrics when both adapters are present', async () => {
    apiGetMock.mockResolvedValueOnce([warehouseAdapter, fakeAdapter]);

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
    apiGetMock.mockResolvedValueOnce([warehouseAdapter, demoAdapter]);

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

  it('defaults to live mode when the warehouse adapter is available even if dummy was persisted', async () => {
    useDatasetStore.setState({
      mode: 'dummy',
      adapters: [],
      source: 'fake',
    });
    apiGetMock.mockResolvedValueOnce([warehouseAdapter, fakeAdapter]);

    await useDatasetStore.getState().loadAdapters();

    const state = useDatasetStore.getState();
    expect(state.mode).toBe('live');
    expect(state.source).toBe('warehouse');
  });
});
