import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import EmptyState from '../../components/EmptyState';
import WorkspaceHeader from '../../components/google-ads/workspace/WorkspaceHeader';
import WorkspaceInsightsRail from '../../components/google-ads/workspace/WorkspaceInsightsRail';
import WorkspaceKpiStrip from '../../components/google-ads/workspace/WorkspaceKpiStrip';
import AssetsTabSection from '../../components/google-ads/workspace/tab-sections/AssetsTabSection';
import CampaignsTabSection from '../../components/google-ads/workspace/tab-sections/CampaignsTabSection';
import ChangesTabSection from '../../components/google-ads/workspace/tab-sections/ChangesTabSection';
import ConversionsTabSection from '../../components/google-ads/workspace/tab-sections/ConversionsTabSection';
import GenericTabSection from '../../components/google-ads/workspace/tab-sections/GenericTabSection';
import OverviewTabSection from '../../components/google-ads/workspace/tab-sections/OverviewTabSection';
import PacingTabSection from '../../components/google-ads/workspace/tab-sections/PacingTabSection';
import PmaxTabSection from '../../components/google-ads/workspace/tab-sections/PmaxTabSection';
import RecommendationsTabSection from '../../components/google-ads/workspace/tab-sections/RecommendationsTabSection';
import ReportsTabSection from '../../components/google-ads/workspace/tab-sections/ReportsTabSection';
import SearchTabSection from '../../components/google-ads/workspace/tab-sections/SearchTabSection';
import type {
  SavedViewRecord,
  SearchMode,
  WorkspaceFilters,
  WorkspaceTab,
} from '../../components/google-ads/workspace/types';
import useGoogleAdsWorkspaceData from '../../hooks/useGoogleAdsWorkspaceData';
import { download } from '../../lib/apiClient';
import useDashboardStore from '../../state/useDashboardStore';
import { saveBlobAsFile } from '../../lib/download';
import {
  createGoogleAdsExport,
  createGoogleAdsSavedView,
  fetchGoogleAdsChangeEventsPage,
  fetchGoogleAdsSavedViews,
  updateGoogleAdsSavedView,
} from '../../lib/googleAdsDashboard';

import '../../styles/googleAdsWorkspace.css';

const TAB_CONFIG: Array<{ id: WorkspaceTab; label: string }> = [
  { id: 'overview', label: 'Overview' },
  { id: 'campaigns', label: 'Campaigns' },
  { id: 'search', label: 'Search & Keywords' },
  { id: 'pmax', label: 'PMax' },
  { id: 'assets', label: 'Assets & Policy' },
  { id: 'conversions', label: 'Conversions' },
  { id: 'pacing', label: 'Pacing' },
  { id: 'changes', label: 'Changes' },
  { id: 'recommendations', label: 'Recommendations' },
  { id: 'reports', label: 'Reports' },
];

function isWorkspaceTab(value: string | null): value is WorkspaceTab {
  return TAB_CONFIG.some((tab) => tab.id === value);
}

function isSearchMode(value: string | null): value is SearchMode {
  return value === 'keywords' || value === 'search_terms' || value === 'insights';
}

function defaultDateRange(): { startDate: string; endDate: string } {
  const end = new Date();
  const start = new Date(end.getTime() - 29 * 24 * 60 * 60 * 1000);
  const toIsoDate = (value: Date) => value.toISOString().slice(0, 10);
  return { startDate: toIsoDate(start), endDate: toIsoDate(end) };
}

function parseFilters(searchParams: URLSearchParams): WorkspaceFilters {
  const defaults = defaultDateRange();
  const compareRaw = searchParams.get('compare');
  const compare =
    compareRaw === 'dod' || compareRaw === 'wow' || compareRaw === 'mom' || compareRaw === 'yoy'
      ? compareRaw
      : 'none';

  return {
    startDate: searchParams.get('start_date') || defaults.startDate,
    endDate: searchParams.get('end_date') || defaults.endDate,
    compare,
    customerId: searchParams.get('customer_id') || '',
    campaignId: searchParams.get('campaign_id') || '',
  };
}

const GoogleAdsWorkspacePage = () => {
  const [searchParams, setSearchParams] = useSearchParams();

  // Subscribe to the global FilterBar store so client/account selection propagates here.
  const globalAccountId = useDashboardStore((state) => state.filters.accountId);
  const globalClientId = useDashboardStore((state) => state.filters.clientId);

  const activeTab: WorkspaceTab = isWorkspaceTab(searchParams.get('tab'))
    ? (searchParams.get('tab') as WorkspaceTab)
    : 'overview';
  const searchMode: SearchMode = isSearchMode(searchParams.get('search_mode'))
    ? (searchParams.get('search_mode') as SearchMode)
    : 'keywords';
  const drawerRaw = searchParams.get('drawer') || '';
  const drawerCampaignId = drawerRaw.startsWith('campaign:')
    ? drawerRaw.replace('campaign:', '')
    : '';

  // Prefer global store's accountId/clientId over URL params so the FilterBar
  // is the authoritative source. URL customer_id serves as a fallback for direct
  // links and saved views.
  const urlFilters = useMemo(() => parseFilters(searchParams), [searchParams]);
  const filters = useMemo((): WorkspaceFilters => {
    // globalAccountId → customer_id; globalClientId → client_id (backend resolves it).
    // URL params serve as fallback for saved-view deep links only.
    const resolvedCustomerId = globalAccountId.trim() || urlFilters.customerId;
    const resolvedClientId = globalClientId.trim() || '';
    return { ...urlFilters, customerId: resolvedCustomerId, clientId: resolvedClientId };
  }, [urlFilters, globalAccountId, globalClientId]);

  // Empty state: no account/client selected anywhere (neither global store nor URL fallback)
  const hasNoCustomer = !filters.customerId && !filters.clientId;

  const { summary, summaryStatus, summaryError, tabStates, loadTab } = useGoogleAdsWorkspaceData({
    filters,
    activeTab,
    searchMode,
  });

  // Architect §4/§6.3: when the Search tab is active in `keywords` mode, also
  // prefetch `search_terms` once so the top-10 bar chart has data. Fire-and-
  // forget; errors swallowed so a search-terms outage doesn't block keywords.
  useEffect(() => {
    if (typeof loadTab !== 'function') return;
    if (activeTab === 'search' && searchMode === 'keywords') {
      const maybe = loadTab('search', 'search_terms');
      if (maybe && typeof (maybe as Promise<unknown>).catch === 'function') {
        void (maybe as Promise<unknown>).catch(() => undefined);
      }
    }
    // When the Overview tab is active, prefetch campaigns so the channel
    // pie has data to derive from (architect §4).
    if (activeTab === 'overview') {
      const maybe = loadTab('campaigns', searchMode);
      if (maybe && typeof (maybe as Promise<unknown>).catch === 'function') {
        void (maybe as Promise<unknown>).catch(() => undefined);
      }
    }
  }, [activeTab, searchMode, loadTab]);

  const tabStateKey = `${activeTab}|${searchMode}`;
  const activeTabState = tabStates[tabStateKey] ?? {
    status: 'idle' as const,
    data: null,
    error: '',
    requestKey: '',
  };

  const [savedViews, setSavedViews] = useState<SavedViewRecord[]>([]);
  const [selectedSavedViewId, setSelectedSavedViewId] = useState('');
  const [headerBusy, setHeaderBusy] = useState(false);

  const loadSavedViews = useCallback(async () => {
    try {
      const rows = await fetchGoogleAdsSavedViews();
      setSavedViews(rows);
    } catch {
      setSavedViews([]);
    }
  }, []);

  useEffect(() => {
    void loadSavedViews();
  }, [loadSavedViews]);

  const updateSearchParams = useCallback(
    (updates: Record<string, string | null>) => {
      const next = new URLSearchParams(searchParams);
      Object.entries(updates).forEach(([key, value]) => {
        if (!value) {
          next.delete(key);
          return;
        }
        next.set(key, value);
      });
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  // B1: The global FilterBar is now shown on /dashboards/google-ads routes.
  // customerId is sourced from useDashboardStore.filters.accountId/clientId in
  // real-time above. The URL customer_id param serves as a fallback for saved-view
  // deep links only. No seed effect needed.

  const handleFilterChange = useCallback(
    (nextFilters: WorkspaceFilters) => {
      updateSearchParams({
        start_date: nextFilters.startDate,
        end_date: nextFilters.endDate,
        compare: nextFilters.compare,
        customer_id: nextFilters.customerId || null,
        campaign_id: nextFilters.campaignId || null,
      });
    },
    [updateSearchParams],
  );

  const handleSelectSavedView = useCallback(
    (id: string) => {
      setSelectedSavedViewId(id);
      if (!id) {
        return;
      }
      const selected = savedViews.find((view) => view.id === id);
      if (!selected) {
        return;
      }
      const viewFilters = (selected.filters ?? {}) as Record<string, unknown>;
      updateSearchParams({
        start_date:
          typeof viewFilters.start_date === 'string' ? viewFilters.start_date : filters.startDate,
        end_date: typeof viewFilters.end_date === 'string' ? viewFilters.end_date : filters.endDate,
        compare: typeof viewFilters.compare === 'string' ? viewFilters.compare : filters.compare,
        customer_id: typeof viewFilters.customer_id === 'string' ? viewFilters.customer_id : null,
        campaign_id: typeof viewFilters.campaign_id === 'string' ? viewFilters.campaign_id : null,
      });
      // CC2 fix: restore client_id from saved view into the global store so
      // the workspace fetches are scoped to the correct MCC client account.
      // If the saved view has no client_id, clear the store's clientId so a
      // stale selection from a previous session does not contaminate this view.
      if (typeof viewFilters.client_id === 'string') {
        const storeFilters = useDashboardStore.getState().filters;
        useDashboardStore
          .getState()
          .setFilters({ ...storeFilters, clientId: viewFilters.client_id });
      }
    },
    [savedViews, updateSearchParams, filters],
  );

  const handleSaveView = useCallback(async () => {
    const suggestedName = `Workspace ${new Date().toISOString().slice(0, 10)}`;
    setHeaderBusy(true);
    try {
      const created = await createGoogleAdsSavedView({
        name: suggestedName,
        description: 'Unified Google Ads workspace filters',
        filters: {
          start_date: filters.startDate,
          end_date: filters.endDate,
          compare: filters.compare,
          customer_id: filters.customerId,
          campaign_id: filters.campaignId,
        },
        is_shared: false,
      });
      setSelectedSavedViewId(created.id);
      await loadSavedViews();
    } finally {
      setHeaderBusy(false);
    }
  }, [filters, loadSavedViews]);

  const handleUpdateView = useCallback(async () => {
    if (!selectedSavedViewId) {
      return;
    }
    setHeaderBusy(true);
    try {
      await updateGoogleAdsSavedView(selectedSavedViewId, {
        filters: {
          start_date: filters.startDate,
          end_date: filters.endDate,
          compare: filters.compare,
          customer_id: filters.customerId,
          campaign_id: filters.campaignId,
        },
      });
      await loadSavedViews();
    } finally {
      setHeaderBusy(false);
    }
  }, [filters, loadSavedViews, selectedSavedViewId]);

  const handleExport = useCallback(
    async (format: 'csv' | 'pdf') => {
      setHeaderBusy(true);
      try {
        const job = await createGoogleAdsExport({
          export_format: format,
          name: `Google Ads ${activeTab} ${new Date().toISOString().slice(0, 10)}`,
          filters: {
            start_date: filters.startDate,
            end_date: filters.endDate,
            compare: filters.compare,
            customer_id: filters.customerId,
            campaign_id: filters.campaignId,
          },
        });
        if (job.download_url) {
          const { blob, filename } = await download(job.download_url);
          saveBlobAsFile(blob, filename || `google_ads_export_${job.id}.csv`);
        }
      } finally {
        setHeaderBusy(false);
      }
    },
    [activeTab, filters],
  );

  const renderTabContent = () => {
    if (activeTab === 'overview') {
      // Architect §4: channel pie requires campaigns-tab cache (not summary).
      // Reads whatever is already in the tab cache; EmptyState shows when
      // campaigns haven't been loaded yet.
      const campaignsCacheKey = `campaigns|${searchMode}`;
      const cached = tabStates[campaignsCacheKey]?.data as { results?: unknown[] } | undefined;
      const campaignRows = Array.isArray(cached?.results)
        ? (cached?.results as Array<Record<string, unknown>>)
        : null;
      return <OverviewTabSection summary={summary} campaignRows={campaignRows} />;
    }

    if (activeTab === 'campaigns') {
      return (
        <CampaignsTabSection
          data={activeTabState.data}
          status={activeTabState.status}
          error={activeTabState.error}
          drawerCampaignId={drawerCampaignId}
          onOpenDrawer={(campaignId) =>
            updateSearchParams({ drawer: campaignId ? `campaign:${campaignId}` : null })
          }
          onCloseDrawer={() => updateSearchParams({ drawer: null })}
        />
      );
    }

    if (activeTab === 'search') {
      // Pull the prefetched search_terms cache for the top-10 chart.
      const searchTermsCache = tabStates['search|search_terms']?.data as
        | { results?: unknown[] }
        | undefined;
      const searchTermRows = Array.isArray(searchTermsCache?.results)
        ? (searchTermsCache?.results as Array<Record<string, unknown>>)
        : null;
      return (
        <>
          <section className="panel" style={{ marginBottom: '1rem' }}>
            <div
              className="dashboard-header__actions-row"
              role="group"
              aria-label="Search data mode"
            >
              <button
                type="button"
                className={`button secondary${searchMode === 'keywords' ? ' is-active' : ''}`}
                onClick={() => updateSearchParams({ search_mode: 'keywords' })}
              >
                Keywords
              </button>
              <button
                type="button"
                className={`button secondary${searchMode === 'search_terms' ? ' is-active' : ''}`}
                onClick={() => updateSearchParams({ search_mode: 'search_terms' })}
              >
                Search Terms
              </button>
              <button
                type="button"
                className={`button secondary${searchMode === 'insights' ? ' is-active' : ''}`}
                onClick={() => updateSearchParams({ search_mode: 'insights' })}
              >
                Insights
              </button>
            </div>
          </section>
          <SearchTabSection
            searchMode={searchMode}
            data={activeTabState.data}
            status={activeTabState.status}
            error={activeTabState.error}
            searchTermRows={searchTermRows}
          />
        </>
      );
    }

    if (activeTab === 'pacing') {
      return (
        <PacingTabSection
          data={activeTabState.data}
          status={activeTabState.status}
          error={activeTabState.error}
        />
      );
    }

    if (activeTab === 'changes') {
      return (
        <ChangesTabSection
          data={activeTabState.data}
          status={activeTabState.status}
          error={activeTabState.error}
          loadMore={(cursor) =>
            fetchGoogleAdsChangeEventsPage({
              page: Number(cursor),
              start_date: filters.startDate,
              end_date: filters.endDate,
              customer_id: filters.customerId || undefined,
            })
          }
        />
      );
    }

    if (activeTab === 'recommendations') {
      return (
        <RecommendationsTabSection
          data={activeTabState.data}
          status={activeTabState.status}
          error={activeTabState.error}
        />
      );
    }

    if (activeTab === 'reports') {
      return <ReportsTabSection initialSavedViews={savedViews} />;
    }

    if (activeTab === 'assets') {
      return (
        <AssetsTabSection
          data={activeTabState.data}
          status={activeTabState.status}
          error={activeTabState.error}
        />
      );
    }

    if (activeTab === 'pmax') {
      return (
        <PmaxTabSection
          data={activeTabState.data}
          status={activeTabState.status}
          error={activeTabState.error}
        />
      );
    }

    if (activeTab === 'conversions') {
      return (
        <ConversionsTabSection
          data={activeTabState.data}
          status={activeTabState.status}
          error={activeTabState.error}
          summary={summary}
        />
      );
    }

    return (
      <GenericTabSection
        title={TAB_CONFIG.find((tab) => tab.id === activeTab)?.label ?? activeTab}
        status={activeTabState.status}
        error={activeTabState.error}
        data={activeTabState.data}
      />
    );
  };

  if (hasNoCustomer) {
    return (
      <section className="dashboardPage" aria-labelledby="google-ads-workspace-title">
        <header className="dashboardPageHeader">
          <p className="dashboardEyebrow">Google Ads</p>
          <h1 className="dashboardHeading" id="google-ads-workspace-title">
            Unified Workspace
          </h1>
        </header>
        <EmptyState
          reasonCode="no_customer_selected"
          icon={
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="40"
              height="40"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              aria-hidden="true"
            >
              <circle cx="12" cy="12" r="10" />
              <path d="M12 8v4M12 16h.01" />
            </svg>
          }
          title="No account selected"
          message="Use the Client and Account dropdowns above to select a Google Ads account."
        />
      </section>
    );
  }

  return (
    <section className="dashboardPage" aria-labelledby="google-ads-workspace-title">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Google Ads</p>
        <h1 className="dashboardHeading" id="google-ads-workspace-title">
          Unified Workspace
        </h1>
        <p className="dashboardSubtitle">
          One workspace for executive monitoring, optimization drilldowns, governance, and exports.
        </p>
      </header>

      <WorkspaceHeader
        filters={filters}
        onFiltersChange={handleFilterChange}
        savedViews={savedViews}
        selectedSavedViewId={selectedSavedViewId}
        onSelectSavedView={handleSelectSavedView}
        onSaveView={handleSaveView}
        onUpdateView={handleUpdateView}
        onExport={handleExport}
        busy={headerBusy}
      />

      <WorkspaceKpiStrip summary={summary} status={summaryStatus} error={summaryError} />

      <div className="panel gads-workspace__tabs-panel">
        <div
          className="gads-workspace__tabs"
          role="tablist"
          aria-label="Google Ads workspace sections"
        >
          {TAB_CONFIG.map((tab) => (
            <button
              key={tab.id}
              id={`tab-${tab.id}`}
              role="tab"
              aria-selected={activeTab === tab.id}
              aria-controls={`tabpanel-${tab.id}`}
              className={`button secondary gads-workspace__tab${activeTab === tab.id ? ' is-active' : ''}`}
              type="button"
              onClick={() => updateSearchParams({ tab: tab.id })}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="gads-workspace__content-grid">
        <div role="tabpanel" id={`tabpanel-${activeTab}`} aria-labelledby={`tab-${activeTab}`}>
          {renderTabContent()}
        </div>
        <WorkspaceInsightsRail summary={summary} activeTab={activeTab} />
      </div>
    </section>
  );
};

export default GoogleAdsWorkspacePage;
