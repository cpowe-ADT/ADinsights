import { create } from 'zustand';

import { ApiError } from '../lib/apiClient';
import {
  type MetaAccount,
  type MetaAd,
  type MetaAdSet,
  type MetaCampaign,
  type MetaInsightRecord,
  loadMetaAccounts,
  loadMetaAdSets,
  loadMetaAds,
  loadMetaCampaigns,
  loadMetaInsights,
} from '../lib/meta';

type LoadStatus = 'idle' | 'loading' | 'loaded' | 'stale' | 'error';
type LoadErrorCode = 'permission_error' | 'token_expired' | 'rate_limited' | 'unknown';

type PagedSlice<T> = {
  status: LoadStatus;
  error?: string;
  errorCode?: LoadErrorCode;
  rows: T[];
  count: number;
  page: number;
  pageSize: number;
};

export type MetaFilters = {
  accountId: string;
  campaignId: string;
  adsetId: string;
  level: 'account' | 'campaign' | 'adset' | 'ad';
  since: string;
  until: string;
  search: string;
  status: string;
};

type MetaState = {
  filters: MetaFilters;
  accounts: PagedSlice<MetaAccount>;
  campaigns: PagedSlice<MetaCampaign>;
  adsets: PagedSlice<MetaAdSet>;
  ads: PagedSlice<MetaAd>;
  insights: PagedSlice<MetaInsightRecord>;
  setFilters: (value: Partial<MetaFilters>) => void;
  loadAccounts: () => Promise<void>;
  loadCampaigns: () => Promise<void>;
  loadAdsets: () => Promise<void>;
  loadAds: () => Promise<void>;
  loadInsights: () => Promise<void>;
  retryAll: () => Promise<void>;
};

const initialSlice = <T>(): PagedSlice<T> => ({
  status: 'idle',
  rows: [],
  count: 0,
  page: 1,
  pageSize: 50,
});

function classifyLoadError(
  error: unknown,
  fallbackMessage: string,
): { message: string; code: LoadErrorCode } {
  const status =
    error instanceof ApiError
      ? error.status
      : typeof error === 'object' && error !== null && 'status' in error
        ? Number((error as { status?: unknown }).status)
        : undefined;
  const apiMessage =
    error instanceof ApiError
      ? error.message
      : typeof error === 'object' && error !== null && 'message' in error
        ? String((error as { message?: unknown }).message ?? '')
        : '';

  if (status === 401) {
    return {
      message: apiMessage || 'Meta token expired. Reconnect Meta from Data Sources.',
      code: 'token_expired',
    };
  }
  if (status === 403) {
    return {
      message:
        apiMessage ||
        'Permission denied by Meta. Re-run OAuth with required permissions.',
      code: 'permission_error',
    };
  }
  if (status === 429) {
    return {
      message: apiMessage || 'Meta API rate limit reached. Retry in a moment.',
      code: 'rate_limited',
    };
  }

  if (error instanceof ApiError) {
    return {
      message: apiMessage || fallbackMessage,
      code: 'unknown',
    };
  }
  if (error instanceof Error) {
    return {
      message: error.message || fallbackMessage,
      code: 'unknown',
    };
  }
  return {
    message: fallbackMessage,
    code: 'unknown',
  };
}

function defaultDateRange(): { since: string; until: string } {
  const now = new Date();
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  const since = new Date(yesterday);
  since.setDate(yesterday.getDate() - 29);
  return {
    since: since.toISOString().slice(0, 10),
    until: yesterday.toISOString().slice(0, 10),
  };
}

const dates = defaultDateRange();

export const useMetaStore = create<MetaState>((set, get) => ({
  filters: {
    accountId: '',
    campaignId: '',
    adsetId: '',
    level: 'ad',
    since: dates.since,
    until: dates.until,
    search: '',
    status: '',
  },
  accounts: initialSlice<MetaAccount>(),
  campaigns: initialSlice<MetaCampaign>(),
  adsets: initialSlice<MetaAdSet>(),
  ads: initialSlice<MetaAd>(),
  insights: initialSlice<MetaInsightRecord>(),
  setFilters: (value) => set((state) => ({ filters: { ...state.filters, ...value } })),
  loadAccounts: async () => {
    set((state) => ({
      accounts: {
        ...state.accounts,
        status: 'loading',
        error: undefined,
        errorCode: undefined,
      },
    }));
    try {
      const { filters, accounts } = get();
      const payload = await loadMetaAccounts({
        page: accounts.page,
        page_size: accounts.pageSize,
        search: filters.search,
        status: filters.status,
        since: filters.since,
        until: filters.until,
      });
      set((state) => ({
        accounts: {
          ...state.accounts,
          status: 'loaded',
          rows: payload.results,
          count: payload.count,
          error: undefined,
          errorCode: undefined,
        },
      }));
    } catch (error) {
      const result = classifyLoadError(error, 'Unable to load Meta ad accounts.');
      set((state) => ({
        accounts: {
          ...state.accounts,
          status: state.accounts.rows.length > 0 ? 'stale' : 'error',
          error: result.message,
          errorCode: result.code,
        },
      }));
    }
  },
  loadCampaigns: async () => {
    set((state) => ({
      campaigns: {
        ...state.campaigns,
        status: 'loading',
        error: undefined,
        errorCode: undefined,
      },
    }));
    try {
      const { filters, campaigns } = get();
      const payload = await loadMetaCampaigns({
        page: campaigns.page,
        page_size: campaigns.pageSize,
        account_id: filters.accountId || undefined,
        search: filters.search,
        status: filters.status,
        since: filters.since,
        until: filters.until,
      });
      set((state) => ({
        campaigns: {
          ...state.campaigns,
          status: 'loaded',
          rows: payload.results,
          count: payload.count,
          error: undefined,
          errorCode: undefined,
        },
      }));
    } catch (error) {
      const result = classifyLoadError(error, 'Unable to load Meta campaigns.');
      set((state) => ({
        campaigns: {
          ...state.campaigns,
          status: state.campaigns.rows.length > 0 ? 'stale' : 'error',
          error: result.message,
          errorCode: result.code,
        },
      }));
    }
  },
  loadAdsets: async () => {
    set((state) => ({
      adsets: {
        ...state.adsets,
        status: 'loading',
        error: undefined,
        errorCode: undefined,
      },
    }));
    try {
      const { filters, adsets } = get();
      const payload = await loadMetaAdSets({
        page: adsets.page,
        page_size: adsets.pageSize,
        account_id: filters.accountId || undefined,
        campaign_id: filters.campaignId || undefined,
        search: filters.search,
        status: filters.status,
        since: filters.since,
        until: filters.until,
      });
      set((state) => ({
        adsets: {
          ...state.adsets,
          status: 'loaded',
          rows: payload.results,
          count: payload.count,
          error: undefined,
          errorCode: undefined,
        },
      }));
    } catch (error) {
      const result = classifyLoadError(error, 'Unable to load Meta ad sets.');
      set((state) => ({
        adsets: {
          ...state.adsets,
          status: state.adsets.rows.length > 0 ? 'stale' : 'error',
          error: result.message,
          errorCode: result.code,
        },
      }));
    }
  },
  loadAds: async () => {
    set((state) => ({
      ads: {
        ...state.ads,
        status: 'loading',
        error: undefined,
        errorCode: undefined,
      },
    }));
    try {
      const { filters, ads } = get();
      const payload = await loadMetaAds({
        page: ads.page,
        page_size: ads.pageSize,
        adset_id: filters.adsetId || undefined,
        campaign_id: filters.campaignId || undefined,
        search: filters.search,
        status: filters.status,
        since: filters.since,
        until: filters.until,
      });
      set((state) => ({
        ads: {
          ...state.ads,
          status: 'loaded',
          rows: payload.results,
          count: payload.count,
          error: undefined,
          errorCode: undefined,
        },
      }));
    } catch (error) {
      const result = classifyLoadError(error, 'Unable to load Meta ads.');
      set((state) => ({
        ads: {
          ...state.ads,
          status: state.ads.rows.length > 0 ? 'stale' : 'error',
          error: result.message,
          errorCode: result.code,
        },
      }));
    }
  },
  loadInsights: async () => {
    set((state) => ({
      insights: {
        ...state.insights,
        status: 'loading',
        error: undefined,
        errorCode: undefined,
      },
    }));
    try {
      const { filters, insights } = get();
      const payload = await loadMetaInsights({
        page: insights.page,
        page_size: insights.pageSize,
        account_id: filters.accountId || undefined,
        campaign_id: filters.campaignId || undefined,
        adset_id: filters.adsetId || undefined,
        level: filters.level,
        search: filters.search,
        status: filters.status,
        since: filters.since,
        until: filters.until,
      });
      set((state) => ({
        insights: {
          ...state.insights,
          status: 'loaded',
          rows: payload.results,
          count: payload.count,
          error: undefined,
          errorCode: undefined,
        },
      }));
    } catch (error) {
      const result = classifyLoadError(error, 'Unable to load Meta insights.');
      set((state) => ({
        insights: {
          ...state.insights,
          status: state.insights.rows.length > 0 ? 'stale' : 'error',
          error: result.message,
          errorCode: result.code,
        },
      }));
    }
  },
  retryAll: async () => {
    await Promise.all([get().loadAccounts(), get().loadCampaigns(), get().loadInsights()]);
  },
}));

export default useMetaStore;
