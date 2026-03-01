import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { appendQueryParams, get, type QueryParams } from '../lib/apiClient';
import {
  fetchGoogleAdsWorkspaceSummary,
  type GoogleAdsWorkspaceSummaryResponse,
} from '../lib/googleAdsDashboard';

export type WorkspaceTab =
  | 'overview'
  | 'campaigns'
  | 'search'
  | 'pmax'
  | 'assets'
  | 'conversions'
  | 'pacing'
  | 'changes'
  | 'recommendations'
  | 'reports';

export type SearchMode = 'keywords' | 'search_terms' | 'insights';

export type WorkspaceFilters = {
  startDate: string;
  endDate: string;
  compare: 'none' | 'dod' | 'wow' | 'mom' | 'yoy';
  customerId?: string;
  campaignId?: string;
};

type TabFetchState = {
  status: 'idle' | 'loading' | 'success' | 'error';
  data: unknown;
  error: string;
  requestKey: string;
};

function tabEndpoint(tab: WorkspaceTab, searchMode: SearchMode): string | null {
  switch (tab) {
    case 'campaigns':
      return '/analytics/google-ads/campaigns/';
    case 'search':
      if (searchMode === 'search_terms') {
        return '/analytics/google-ads/search-terms/';
      }
      if (searchMode === 'insights') {
        return '/analytics/google-ads/search-term-insights/';
      }
      return '/analytics/google-ads/keywords/';
    case 'pmax':
      return '/analytics/google-ads/pmax/asset-groups/';
    case 'assets':
      return '/analytics/google-ads/assets/';
    case 'conversions':
      return '/analytics/google-ads/conversions/actions/';
    case 'pacing':
      return '/analytics/google-ads/budgets/pacing/';
    case 'changes':
      return '/analytics/google-ads/change-events/';
    case 'recommendations':
      return '/analytics/google-ads/recommendations/';
    case 'reports':
      return '/analytics/google-ads/saved-views/';
    default:
      return null;
  }
}

function buildCommonParams(filters: WorkspaceFilters): QueryParams {
  return {
    start_date: filters.startDate,
    end_date: filters.endDate,
    compare: filters.compare,
    customer_id: filters.customerId,
    campaign_id: filters.campaignId,
  };
}

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

const useGoogleAdsWorkspaceData = ({
  filters,
  activeTab,
  searchMode,
}: {
  filters: WorkspaceFilters;
  activeTab: WorkspaceTab;
  searchMode: SearchMode;
}) => {
  const baseParams = useMemo(() => buildCommonParams(filters), [filters]);
  const filterKey = useMemo(
    () => [filters.startDate, filters.endDate, filters.compare, filters.customerId ?? '', filters.campaignId ?? ''].join('|'),
    [filters],
  );

  const [summary, setSummary] = useState<GoogleAdsWorkspaceSummaryResponse | null>(null);
  const [summaryStatus, setSummaryStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [summaryError, setSummaryError] = useState('');

  const [tabStates, setTabStates] = useState<Record<string, TabFetchState>>({});

  const summaryCacheRef = useRef(new Map<string, GoogleAdsWorkspaceSummaryResponse>());
  const summaryInflightRef = useRef(new Map<string, Promise<GoogleAdsWorkspaceSummaryResponse>>());
  const tabCacheRef = useRef(new Map<string, unknown>());
  const tabInflightRef = useRef(new Map<string, Promise<unknown>>());

  const loadSummary = useCallback(async () => {
    const cacheKey = filterKey;
    const cached = summaryCacheRef.current.get(cacheKey);
    if (cached) {
      setSummary(cached);
      setSummaryStatus('success');
      setSummaryError('');
      return cached;
    }

    const inflight = summaryInflightRef.current.get(cacheKey);
    if (inflight) {
      setSummaryStatus('loading');
      const result = await inflight;
      setSummary(result);
      setSummaryStatus('success');
      return result;
    }

    setSummaryStatus('loading');
    setSummaryError('');
    const request = fetchGoogleAdsWorkspaceSummary(baseParams)
      .then((response) => {
        summaryCacheRef.current.set(cacheKey, response);
        return response;
      })
      .finally(() => {
        summaryInflightRef.current.delete(cacheKey);
      });
    summaryInflightRef.current.set(cacheKey, request);

    try {
      const result = await request;
      setSummary(result);
      setSummaryStatus('success');
      return result;
    } catch (error) {
      setSummaryStatus('error');
      setSummaryError(getErrorMessage(error, 'Failed to load Google Ads summary.'));
      throw error;
    }
  }, [baseParams, filterKey]);

  const loadTab = useCallback(
    async (tab: WorkspaceTab, mode: SearchMode = searchMode) => {
      if (tab === 'overview') {
        return loadSummary();
      }

      const endpoint = tabEndpoint(tab, mode);
      if (!endpoint) {
        return null;
      }

      const requestKey = `${tab}|${mode}|${filterKey}`;
      const stateKey = `${tab}|${mode}`;

      const cached = tabCacheRef.current.get(requestKey);
      if (cached !== undefined) {
        setTabStates((prev) => ({
          ...prev,
          [stateKey]: {
            status: 'success',
            data: cached,
            error: '',
            requestKey,
          },
        }));
        return cached;
      }

      setTabStates((prev) => ({
        ...prev,
        [stateKey]: {
          status: 'loading',
          data: prev[stateKey]?.data,
          error: '',
          requestKey,
        },
      }));

      const inflight = tabInflightRef.current.get(requestKey);
      if (inflight) {
        return inflight;
      }

      const path = appendQueryParams(endpoint, baseParams);
      const request = get<unknown>(path)
        .then((result) => {
          tabCacheRef.current.set(requestKey, result);
          return result;
        })
        .finally(() => {
          tabInflightRef.current.delete(requestKey);
        });
      tabInflightRef.current.set(requestKey, request);

      try {
        const result = await request;
        setTabStates((prev) => ({
          ...prev,
          [stateKey]: {
            status: 'success',
            data: result,
            error: '',
            requestKey,
          },
        }));
        return result;
      } catch (error) {
        setTabStates((prev) => ({
          ...prev,
          [stateKey]: {
            status: 'error',
            data: null,
            error: getErrorMessage(error, 'Failed to load tab data.'),
            requestKey,
          },
        }));
        throw error;
      }
    },
    [baseParams, filterKey, loadSummary, searchMode],
  );

  useEffect(() => {
    void loadSummary();
  }, [loadSummary]);

  useEffect(() => {
    void loadTab(activeTab, searchMode);
  }, [activeTab, loadTab, searchMode]);

  return {
    summary,
    summaryStatus,
    summaryError,
    loadSummary,
    tabStates,
    loadTab,
    filterKey,
  };
};

export default useGoogleAdsWorkspaceData;
