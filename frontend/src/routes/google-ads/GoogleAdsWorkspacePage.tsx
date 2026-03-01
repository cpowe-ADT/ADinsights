import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import WorkspaceHeader from '../../components/google-ads/workspace/WorkspaceHeader';
import WorkspaceInsightsRail from '../../components/google-ads/workspace/WorkspaceInsightsRail';
import WorkspaceKpiStrip from '../../components/google-ads/workspace/WorkspaceKpiStrip';
import CampaignsTabSection from '../../components/google-ads/workspace/tab-sections/CampaignsTabSection';
import GenericTabSection from '../../components/google-ads/workspace/tab-sections/GenericTabSection';
import OverviewTabSection from '../../components/google-ads/workspace/tab-sections/OverviewTabSection';
import type {
  SavedViewRecord,
  SearchMode,
  WorkspaceFilters,
  WorkspaceTab,
} from '../../components/google-ads/workspace/types';
import useGoogleAdsWorkspaceData from '../../hooks/useGoogleAdsWorkspaceData';
import { download } from '../../lib/apiClient';
import { saveBlobAsFile } from '../../lib/download';
import {
  createGoogleAdsExport,
  createGoogleAdsSavedView,
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
  const compare = compareRaw === 'dod' || compareRaw === 'wow' || compareRaw === 'mom' || compareRaw === 'yoy' ? compareRaw : 'none';

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

  const activeTab: WorkspaceTab = isWorkspaceTab(searchParams.get('tab')) ? (searchParams.get('tab') as WorkspaceTab) : 'overview';
  const searchMode: SearchMode = isSearchMode(searchParams.get('search_mode'))
    ? (searchParams.get('search_mode') as SearchMode)
    : 'keywords';
  const drawerRaw = searchParams.get('drawer') || '';
  const drawerCampaignId = drawerRaw.startsWith('campaign:') ? drawerRaw.replace('campaign:', '') : '';

  const filters = useMemo(() => parseFilters(searchParams), [searchParams]);

  const {
    summary,
    summaryStatus,
    summaryError,
    tabStates,
  } = useGoogleAdsWorkspaceData({ filters, activeTab, searchMode });

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
        start_date: typeof viewFilters.start_date === 'string' ? viewFilters.start_date : filters.startDate,
        end_date: typeof viewFilters.end_date === 'string' ? viewFilters.end_date : filters.endDate,
        compare: typeof viewFilters.compare === 'string' ? viewFilters.compare : filters.compare,
        customer_id: typeof viewFilters.customer_id === 'string' ? viewFilters.customer_id : null,
        campaign_id: typeof viewFilters.campaign_id === 'string' ? viewFilters.campaign_id : null,
      });
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
      return <OverviewTabSection summary={summary} />;
    }

    if (activeTab === 'campaigns') {
      return (
        <CampaignsTabSection
          data={activeTabState.data}
          status={activeTabState.status}
          error={activeTabState.error}
          drawerCampaignId={drawerCampaignId}
          onOpenDrawer={(campaignId) => updateSearchParams({ drawer: campaignId ? `campaign:${campaignId}` : null })}
          onCloseDrawer={() => updateSearchParams({ drawer: null })}
        />
      );
    }

    if (activeTab === 'search') {
      return (
        <>
          <section className="panel" style={{ marginBottom: '1rem' }}>
            <div className="dashboard-header__actions-row" role="group" aria-label="Search data mode">
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
          <GenericTabSection
            title="Search & Keywords"
            status={activeTabState.status}
            error={activeTabState.error}
            data={activeTabState.data}
          />
        </>
      );
    }

    if (activeTab === 'pacing') {
      return (
        <GenericTabSection
          title="Budget & pacing"
          description="Month-to-date pacing, forecast, and risk signals."
          status={activeTabState.status}
          error={activeTabState.error}
          data={activeTabState.data}
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
        <div className="gads-workspace__tabs" role="tablist" aria-label="Google Ads workspace sections">
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
