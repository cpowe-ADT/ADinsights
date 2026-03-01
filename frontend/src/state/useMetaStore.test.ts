import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../lib/apiClient';

const metaMocks = vi.hoisted(() => ({
  loadMetaAccounts: vi.fn(),
  loadMetaCampaigns: vi.fn(),
  loadMetaAdSets: vi.fn(),
  loadMetaAds: vi.fn(),
  loadMetaInsights: vi.fn(),
}));

vi.mock('../lib/meta', () => ({
  loadMetaAccounts: metaMocks.loadMetaAccounts,
  loadMetaCampaigns: metaMocks.loadMetaCampaigns,
  loadMetaAdSets: metaMocks.loadMetaAdSets,
  loadMetaAds: metaMocks.loadMetaAds,
  loadMetaInsights: metaMocks.loadMetaInsights,
}));

describe('useMetaStore', () => {
  beforeEach(async () => {
    vi.resetModules();
    vi.clearAllMocks();
    const { default: useMetaStore } = await import('./useMetaStore');
    useMetaStore.setState({
      filters: {
        accountId: '',
        campaignId: '',
        adsetId: '',
        level: 'ad',
        since: '2026-01-01',
        until: '2026-01-31',
        search: '',
        status: '',
      },
      accounts: { status: 'idle', rows: [], count: 0, page: 1, pageSize: 50 },
      campaigns: { status: 'idle', rows: [], count: 0, page: 1, pageSize: 50 },
      adsets: { status: 'idle', rows: [], count: 0, page: 1, pageSize: 50 },
      ads: { status: 'idle', rows: [], count: 0, page: 1, pageSize: 50 },
      insights: { status: 'idle', rows: [], count: 0, page: 1, pageSize: 50 },
    });
  });

  it('loads accounts and campaigns into store state', async () => {
    metaMocks.loadMetaAccounts.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: '1',
          external_id: 'act_123',
          account_id: '123',
          name: 'Primary',
          currency: 'USD',
          status: '1',
          business_name: 'Biz',
          metadata: {},
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ],
    });
    metaMocks.loadMetaCampaigns.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: 'c1',
          external_id: 'cmp-1',
          name: 'Campaign 1',
          platform: 'meta',
          status: 'ACTIVE',
          objective: 'LINK_CLICKS',
          currency: 'USD',
          account_external_id: 'act_123',
          metadata: {},
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ],
    });

    const { default: useMetaStore } = await import('./useMetaStore');
    await useMetaStore.getState().loadAccounts();
    await useMetaStore.getState().loadCampaigns();

    const state = useMetaStore.getState();
    expect(state.accounts.status).toBe('loaded');
    expect(state.accounts.rows).toHaveLength(1);
    expect(state.campaigns.status).toBe('loaded');
    expect(state.campaigns.rows[0]?.external_id).toBe('cmp-1');
  });

  it('sets error state and recovers on retryAll', async () => {
    metaMocks.loadMetaAccounts.mockRejectedValueOnce(new Error('429 from API')).mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });
    metaMocks.loadMetaCampaigns.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });
    metaMocks.loadMetaInsights.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });

    const { default: useMetaStore } = await import('./useMetaStore');
    await useMetaStore.getState().loadAccounts();
    expect(useMetaStore.getState().accounts.status).toBe('error');
    expect(useMetaStore.getState().accounts.error).toContain('429');

    await useMetaStore.getState().retryAll();
    expect(useMetaStore.getState().accounts.status).toBe('loaded');
    expect(metaMocks.loadMetaAccounts).toHaveBeenCalledTimes(2);
  });

  it('marks stale data when refresh fails but prior rows exist', async () => {
    metaMocks.loadMetaAccounts.mockRejectedValueOnce(
      new ApiError('Rate limited', 429, { detail: 'Rate limited' }),
    );

    const { default: useMetaStore } = await import('./useMetaStore');
    useMetaStore.setState((state) => ({
      accounts: {
        ...state.accounts,
        status: 'loaded',
        rows: [
          {
            id: '1',
            external_id: 'act_123',
            account_id: '123',
            name: 'Primary',
            currency: 'USD',
            status: '1',
            business_name: 'Biz',
            metadata: {},
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:00:00Z',
          },
        ],
        count: 1,
      },
    }));

    await useMetaStore.getState().loadAccounts();
    const state = useMetaStore.getState();
    expect(state.accounts.status).toBe('stale');
    expect(state.accounts.errorCode).toBe('rate_limited');
    expect(state.accounts.rows).toHaveLength(1);
  });

  it('classifies 403 responses as permission errors', async () => {
    metaMocks.loadMetaAccounts.mockRejectedValueOnce(
      new ApiError('Forbidden', 403, { detail: 'Forbidden' }),
    );

    const { default: useMetaStore } = await import('./useMetaStore');
    await useMetaStore.getState().loadAccounts();
    const state = useMetaStore.getState();
    expect(state.accounts.status).toBe('error');
    expect(state.accounts.errorCode).toBe('permission_error');
  });
});
