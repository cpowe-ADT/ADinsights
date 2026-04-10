import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Link,
  NavLink,
  Outlet,
  useLocation,
  useNavigate,
  type NavLinkRenderProps,
} from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import Breadcrumbs from '../components/Breadcrumbs';
import FilterBar, {
  type FilterBarAccountOption,
  type FilterBarState,
} from '../components/FilterBar';
import { useTheme } from '../components/ThemeProvider';
import { useToast } from '../components/ToastProvider';
import { loadDashboardLayout, saveDashboardLayout } from '../lib/layoutPreferences';
import {
  loadSocialConnectionStatus,
  type SocialPlatformStatusRecord,
} from '../lib/airbyte';
import {
  buildLiveAccountOption,
  chooseDefaultLiveAccountOptionId,
  setLastLiveAccountId,
  sortLiveAccountOptions,
} from '../lib/liveAccountSelection';
import { loadMetaAccounts } from '../lib/meta';
import { canAccessCreatorUi } from '../lib/rbac';
import { formatAbsoluteTime, formatRelativeTime, isTimestampStale } from '../lib/format';
import { MOCK_MODE } from '../lib/apiClient';
import { messageForLiveDatasetReason } from '../lib/datasetStatus';
import {
  areFiltersEqual,
  createDefaultFilterState,
  parseFilterQueryParams,
  serializeFilterQueryParams,
} from '../lib/dashboardFilters';
import DatasetToggle from '../components/DatasetToggle';
import TenantSwitcher from '../components/TenantSwitcher';
import SnapshotIndicator from '../components/SnapshotIndicator';
import StatusBanner from '../components/StatusBanner';
import useDashboardStore from '../state/useDashboardStore';
import { useDatasetStore } from '../state/useDatasetStore';
const metricOptions = [
  { value: 'spend', label: 'Spend' },
  { value: 'impressions', label: 'Impressions' },
  { value: 'reach', label: 'Reach' },
  { value: 'clicks', label: 'Clicks' },
  { value: 'ctr', label: 'CTR' },
  { value: 'cpc', label: 'CPC' },
  { value: 'cpm', label: 'CPM' },
  { value: 'conversions', label: 'Conversions' },
  { value: 'cpa', label: 'CPA' },
  { value: 'frequency', label: 'Frequency' },
  { value: 'roas', label: 'Conv. / $' },
];

const segmentLabels: Record<string, string> = {
  dashboards: 'Dashboards',
  create: 'Create dashboard',
  campaigns: 'Campaigns',
  creatives: 'Creatives',
  budget: 'Budget pacing',
  'data-sources': 'Data sources',
  meta: 'Meta',
  accounts: 'Accounts',
  insights: 'Insights',
  status: 'Status',
  pages: 'Facebook Pages',
  overview: 'Overview',
  posts: 'Posts',
  google: 'Google',
  'google-ads': 'Google Ads',
  executive: 'Executive overview',
  channels: 'Channel views',
  keywords: 'Keywords & search terms',
  assets: 'Ads & assets',
  pmax: 'Performance Max',
  breakdowns: 'Audience & breakdowns',
  conversions: 'Conversions & attribution',
  'change-log': 'Change log & governance',
  recommendations: 'Recommendations',
  reports: 'Reports & exports',
  map: 'Map',
  saved: 'Saved dashboard',
  uploads: 'CSV uploads',
};

function decodeSegmentValue(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch (error) {
    console.warn('Failed to decode route segment', error);
    return value;
  }
}

const DashboardLayout = () => {
  const { tenantId, logout, user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const { pushToast } = useToast();
  const [isScrolled, setIsScrolled] = useState(false);
  const [accountOptions, setAccountOptions] = useState<FilterBarAccountOption[]>([]);
  const [metaStatus, setMetaStatus] = useState<SocialPlatformStatusRecord | null>(null);
  const [accountOptionsResolved, setAccountOptionsResolved] = useState(false);
  const [metaStatusResolved, setMetaStatusResolved] = useState(false);
  const canCreate = canAccessCreatorUi(user);
  const datasetMode = useDatasetStore((state) => state.mode);
  const datasetLoadStatus = useDatasetStore((state) => state.status);
  const datasetSource = useDatasetStore((state) => state.source);
  const liveReason = useDatasetStore((state) => state.liveReason);
  const liveDetail = useDatasetStore((state) => state.liveDetail);
  const liveSnapshotGeneratedAt = useDatasetStore((state) => state.liveSnapshotGeneratedAt);
  const loadAdapters = useDatasetStore((state) => state.loadAdapters);
  const hasLiveData = datasetSource === 'warehouse' || datasetSource === 'meta_direct';

  const {
    loadAll,
    filters,
    setFilters,
    selectedMetric,
    setSelectedMetric,
    selectedParish,
    setSelectedParish,
    campaign,
    creative,
    budget,
    parish,
    activeTenantLabel,
    lastSnapshotGeneratedAt,
  } = useDashboardStore((state) => ({
    loadAll: state.loadAll,
    filters: state.filters,
    setFilters: state.setFilters,
    selectedMetric: state.selectedMetric,
    setSelectedMetric: state.setSelectedMetric,
    selectedParish: state.selectedParish,
    setSelectedParish: state.setSelectedParish,
    campaign: state.campaign,
    creative: state.creative,
    budget: state.budget,
    parish: state.parish,
    activeTenantLabel: state.activeTenantLabel,
    lastSnapshotGeneratedAt: state.lastSnapshotGeneratedAt,
  }));

  const handleFilterChange = useCallback(
    (state: FilterBarState) => {
      if (tenantId && state.accountId.trim() && state.accountId !== filters.accountId) {
        setLastLiveAccountId(tenantId, state.accountId, 'user');
      }
      setFilters(state);
    },
    [filters.accountId, setFilters, tenantId],
  );

  const defaultFilters = useMemo(() => createDefaultFilterState(), []);

  const urlFilters = useMemo(() => {
    const searchParams = new URLSearchParams(location.search);
    return parseFilterQueryParams(searchParams, defaultFilters);
  }, [defaultFilters, location.search]);
  const isSavedDashboardRoute = location.pathname.startsWith('/dashboards/saved/');

  const hideGlobalFilters = useMemo(() => {
    return (
      location.pathname.startsWith('/dashboards/meta/pages') ||
      location.pathname.startsWith('/dashboards/meta/posts') ||
      location.pathname.startsWith('/dashboards/google-ads') ||
      location.pathname.startsWith('/dashboards/create')
    );
  }, [location.pathname]);

  // URL → filters sync: only react to URL changes, not programmatic filter updates.
  // Reading current filters via getState() avoids adding `filters` to the dep array,
  // which previously caused an infinite render loop with the filters→URL effect below.
  useEffect(() => {
    if (isSavedDashboardRoute) {
      return;
    }
    const currentFilters = useDashboardStore.getState().filters;
    if (!areFiltersEqual(currentFilters, urlFilters)) {
      setFilters(urlFilters);
    }
  }, [isSavedDashboardRoute, setFilters, urlFilters]);

  // In mock/e2e mode, DatasetToggle is hidden so it won't call loadAdapters.
  // Load adapters here so liveReason is populated for status banners in tests.
  useEffect(() => {
    if (!MOCK_MODE) {
      return;
    }
    if (datasetLoadStatus !== 'idle') {
      return;
    }
    void loadAdapters();
  }, [datasetLoadStatus, loadAdapters]);

  useEffect(() => {
    let cancelled = false;

    if (!hasLiveData) {
      setAccountOptionsResolved(true);
      setAccountOptions([]);
      return () => {
        cancelled = true;
      };
    }

    setAccountOptionsResolved(false);
    void loadMetaAccounts({ page_size: 200 })
      .then((payload) => {
        if (cancelled) {
          return;
        }
        const options = sortLiveAccountOptions(
          payload.results
            .map((account) => buildLiveAccountOption(account))
            .filter((option): option is FilterBarAccountOption => option !== null),
        );
        setAccountOptions(options);
        setAccountOptionsResolved(true);
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }
        console.warn('Failed to load dashboard client accounts', error);
        setAccountOptions([]);
        setAccountOptionsResolved(true);
      });

    return () => {
      cancelled = true;
    };
  }, [hasLiveData, tenantId]);

  useEffect(() => {
    let cancelled = false;

    setMetaStatusResolved(false);
    void loadSocialConnectionStatus()
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setMetaStatus(payload.platforms.find((row) => row.platform === 'meta') ?? null);
        setMetaStatusResolved(true);
      })
      .catch(() => {
        if (!cancelled) {
          setMetaStatus(null);
          setMetaStatusResolved(true);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!tenantId || !hasLiveData || !accountOptionsResolved || !metaStatusResolved) {
      return;
    }
    if (accountOptions.length === 0) {
      return;
    }

    const validAccountIds = accountOptions.map((option) => option.value);
    const currentAccountId = filters.accountId.trim();
    if (currentAccountId && validAccountIds.includes(currentAccountId)) {
      return;
    }

    const preferredAccountIds = [
      typeof metaStatus?.metadata?.['credential_account_id'] === 'string'
        ? metaStatus.metadata['credential_account_id']
        : '',
    ];
    const defaultAccountId = chooseDefaultLiveAccountOptionId(
      accountOptions,
      tenantId,
      preferredAccountIds,
    );
    if (!defaultAccountId) {
      return;
    }

    setLastLiveAccountId(tenantId, defaultAccountId, 'auto');
    setFilters({
      ...filters,
      accountId: defaultAccountId,
    });
  }, [
    accountOptions,
    accountOptionsResolved,
    filters,
    hasLiveData,
    metaStatus,
    metaStatusResolved,
    setFilters,
    tenantId,
  ]);

  useEffect(() => {
    const nextSearch = serializeFilterQueryParams(filters);
    const currentSearch = location.search.replace(/^\?/, '');
    if (nextSearch === currentSearch) {
      return;
    }
    const nextPath = nextSearch ? `${location.pathname}?${nextSearch}` : location.pathname;
    navigate(nextPath, { replace: true });
  }, [filters, location.pathname, location.search, navigate]);

  const shellRef = useRef<HTMLDivElement>(null);
  const dashboardTopRef = useRef<HTMLDivElement>(null);
  const layoutHydratedRef = useRef(false);

  useEffect(() => {
    if (!MOCK_MODE) {
      if (datasetLoadStatus === 'idle' || datasetLoadStatus === 'loading') {
        return;
      }

      if (!datasetSource) {
        return;
      }
    }

    if (hasLiveData) {
      if (!accountOptionsResolved || !metaStatusResolved) {
        return;
      }
      if (accountOptions.length > 0 && !filters.accountId.trim()) {
        return;
      }
    }

    const delay = filters.campaignQuery.trim().length > 0 ? 350 : 0;
    const handle = window.setTimeout(() => {
      void loadAll(tenantId);
    }, delay);
    return () => window.clearTimeout(handle);
  }, [
    accountOptions.length,
    accountOptionsResolved,
    datasetLoadStatus,
    datasetSource,
    filters,
    hasLiveData,
    loadAll,
    metaStatusResolved,
    tenantId,
  ]);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 4);
    };

    handleScroll();
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return undefined;
    }

    const shell = shellRef.current;
    const dashboardTop = dashboardTopRef.current;
    if (!shell || !dashboardTop) {
      return undefined;
    }

    const updateHeight = () => {
      const nextHeight = dashboardTop.getBoundingClientRect().height;
      shell.style.setProperty('--dashboard-top-height', `${Math.ceil(nextHeight)}px`);
    };

    updateHeight();

    const observer =
      typeof ResizeObserver === 'undefined'
        ? null
        : new ResizeObserver(() => {
            updateHeight();
          });

    observer?.observe(dashboardTop);
    window.addEventListener('resize', updateHeight, { passive: true });

    return () => {
      observer?.disconnect();
      window.removeEventListener('resize', updateHeight);
      shell.style.removeProperty('--dashboard-top-height');
    };
  }, []);

  useEffect(() => {
    if (layoutHydratedRef.current) {
      return;
    }

    layoutHydratedRef.current = true;
    const storedLayout = loadDashboardLayout();
    if (!storedLayout) {
      return;
    }

    if (storedLayout.metric && storedLayout.metric !== selectedMetric) {
      setSelectedMetric(storedLayout.metric);
    }

    if (storedLayout.parish) {
      setSelectedParish(storedLayout.parish);
    }
  }, [selectedMetric, setSelectedMetric, setSelectedParish]);

  const errors = useMemo(() => {
    const warehouseLiveBlocked =
      datasetMode === 'live' && datasetSource === 'warehouse' && liveReason && liveReason !== 'ready';
    return Array.from(
      new Set(
        [campaign, creative, budget, parish]
          .filter((slice) => slice.status === 'error' && slice.error)
          .filter((slice) => {
            if (!warehouseLiveBlocked || !slice.error) {
              return true;
            }
            return !/live warehouse metrics are unavailable|snapshot is stale|default fallback payload/i.test(
              slice.error,
            );
          })
          .map((slice) => slice.error as string),
      ),
    );
  }, [budget, campaign, creative, datasetMode, datasetSource, liveReason, parish]);

  type NavGroup = {
    label: string;
    links: Array<{ label: string; to: string; end: boolean }>;
  };

  const navGroups: NavGroup[] = useMemo(() => [
    {
      label: 'Dashboards',
      links: [
        { label: 'Library', to: '/dashboards', end: true },
        ...(canCreate ? [{ label: 'Create', to: '/dashboards/create', end: false }] : []),
        { label: 'Campaigns', to: '/dashboards/campaigns', end: false },
        { label: 'Creatives', to: '/dashboards/creatives', end: false },
        { label: 'Budget pacing', to: '/dashboards/budget', end: false },
        { label: 'Parish map', to: '/dashboards/map', end: false },
      ],
    },
    {
      label: 'Integrations',
      links: [
        { label: 'Meta accounts', to: '/dashboards/meta/accounts', end: false },
        { label: 'Meta insights', to: '/dashboards/meta/insights', end: false },
        { label: 'Facebook pages', to: '/dashboards/meta/pages', end: false },
        { label: 'GA4', to: '/dashboards/web/ga4', end: false },
        { label: 'Search Console', to: '/dashboards/web/search-console', end: false },
        { label: 'Google Ads', to: '/dashboards/google-ads', end: false },
        { label: 'Data sources', to: '/dashboards/data-sources', end: false },
        { label: 'CSV uploads', to: '/dashboards/uploads', end: false },
      ],
    },
    {
      label: 'Reporting',
      links: [
        { label: 'Reports', to: '/reports', end: false },
      ],
    },
    {
      label: 'Alerts & AI',
      links: [
        { label: 'Alerts', to: '/alerts', end: false },
        { label: 'Summaries', to: '/summaries', end: false },
      ],
    },
    {
      label: 'Operations',
      links: [
        { label: 'Sync Health', to: '/ops/sync-health', end: false },
        { label: 'Health Overview', to: '/ops/health', end: false },
        { label: 'Audit Log', to: '/ops/audit', end: false },
        { label: 'Notifications', to: '/settings/notifications', end: false },
      ],
    },
  ], [canCreate]);

  const campaignLookup = useMemo(() => {
    const rows = campaign.data?.rows ?? [];
    return rows.reduce<Record<string, string>>((acc, row) => {
      acc[row.id] = row.name;
      return acc;
    }, {});
  }, [campaign.data]);

  const creativeLookup = useMemo(() => {
    const rows = creative.data ?? [];
    return rows.reduce<Record<string, string>>((acc, row) => {
      acc[row.id] = row.name;
      return acc;
    }, {});
  }, [creative.data]);

  const breadcrumbs = useMemo(() => {
    const items: { label: string; to?: string }[] = [{ label: 'Home', to: '/' }];
    const segments = location.pathname.split('/').filter(Boolean);
    let pathAccumulator = '';

    segments.forEach((segment, index) => {
      const decodedSegment = decodeSegmentValue(segment);
      pathAccumulator += `/${segment}`;
      let label = segmentLabels[decodedSegment] ?? decodedSegment.replace(/-/g, ' ');

      if (index > 0) {
        const previous = decodeSegmentValue(segments[index - 1]);
        if (previous === 'campaigns') {
          label = campaignLookup[decodedSegment] ?? label;
        } else if (previous === 'creatives') {
          label = creativeLookup[decodedSegment] ?? label;
        }
      }

      items.push({
        label: label.charAt(0).toUpperCase() + label.slice(1),
        to: index === segments.length - 1 ? undefined : pathAccumulator,
      });
    });

    return items;
  }, [campaignLookup, creativeLookup, location.pathname]);

  const handleSaveLayout = useCallback(() => {
    try {
      saveDashboardLayout({ metric: selectedMetric, parish: selectedParish });
      pushToast('Saved layout', { tone: 'success' });
    } catch {
      pushToast('Unable to save layout', { tone: 'error' });
    }
  }, [pushToast, selectedMetric, selectedParish]);

  const handleCopyLink = useCallback(async () => {
    if (typeof window === 'undefined') {
      pushToast('Unable to copy link', { tone: 'error' });
      return;
    }

    const currentUrl = window.location.href;

    try {
      if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
        await navigator.clipboard.writeText(currentUrl);
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = currentUrl;
        textarea.setAttribute('aria-hidden', 'true');
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        textarea.style.pointerEvents = 'none';
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();
        const copied = document.execCommand('copy');
        document.body.removeChild(textarea);
        if (!copied) {
          throw new Error('Copy command failed');
        }
      }

      pushToast('Copied link', { tone: 'success' });
    } catch {
      pushToast('Unable to copy link', { tone: 'error' });
    }
  }, [pushToast]);

  const SaveIcon = (
    <svg
      className="button-icon"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      aria-hidden="true"
    >
      <path d="M5 4h11l3 3v13H5z" />
      <path d="M9 4v5h6V4" />
      <path d="M9 13h6" strokeLinecap="round" />
    </svg>
  );

  const LinkIcon = (
    <svg
      className="button-icon"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      aria-hidden="true"
    >
      <path d="M10.5 7.5 9 6a4 4 0 0 0-5.66 5.66l2 2a4 4 0 0 0 5.66 0" />
      <path d="M13.5 16.5 15 18a4 4 0 0 0 5.66-5.66l-2-2a4 4 0 0 0-5.66 0" />
      <path d="m8 12 8 0" strokeLinecap="round" />
    </svg>
  );

  const accountLabel = (user as { email?: string } | undefined)?.email ?? 'Account';
  const effectiveSnapshotGeneratedAt = liveSnapshotGeneratedAt ?? lastSnapshotGeneratedAt;
  const snapshotRelative = useMemo(
    () => (effectiveSnapshotGeneratedAt ? formatRelativeTime(effectiveSnapshotGeneratedAt) : null),
    [effectiveSnapshotGeneratedAt],
  );
  const snapshotIsStale = isTimestampStale(effectiveSnapshotGeneratedAt, 60);
  const liveStatusMessage = useMemo(
    () => {
      if (datasetMode !== 'live') {
        return null;
      }
      if (!datasetSource) {
        return liveReason ? messageForLiveDatasetReason(liveReason, liveDetail) : null;
      }
      if (datasetSource === 'meta_direct') {
        if (liveReason === 'adapter_disabled') {
          return 'Showing direct Meta sync data. Warehouse reporting is not enabled in this environment.';
        }
        if (liveReason === 'missing_snapshot') {
          return 'Showing direct Meta sync data while the first warehouse snapshot is still pending.';
        }
        if (liveReason === 'stale_snapshot') {
          return 'Showing direct Meta sync data while the warehouse snapshot refresh completes.';
        }
        if (liveReason === 'default_snapshot') {
          return `Showing direct Meta sync data. ${messageForLiveDatasetReason(liveReason, liveDetail)}`;
        }
        return 'Showing direct Meta sync data.';
      }
      return liveReason ? messageForLiveDatasetReason(liveReason, liveDetail) : null;
    },
    [datasetMode, datasetSource, liveDetail, liveReason],
  );
  const snapshotStatusLabel = useMemo(() => {
    if (datasetMode !== 'live') {
      if (!effectiveSnapshotGeneratedAt) {
        return 'Demo dataset active';
      }
      return snapshotRelative
        ? `Demo dataset active - ${snapshotRelative}`
        : 'Demo dataset active';
    }
    if (datasetSource === 'meta_direct') {
      return snapshotRelative ? `Direct Meta sync updated ${snapshotRelative}` : 'Direct Meta sync active';
    }
    if (liveReason === 'adapter_disabled') {
      return 'Live reporting disabled';
    }
    if (liveReason === 'missing_snapshot') {
      return 'Waiting for first live snapshot…';
    }
    if (liveReason === 'stale_snapshot') {
      return 'Live data refreshing…';
    }
    if (liveReason === 'default_snapshot') {
      return 'Fallback live snapshot';
    }
    if (!effectiveSnapshotGeneratedAt) {
      return 'Waiting for live snapshot…';
    }
    return snapshotRelative ? `Updated ${snapshotRelative}` : 'Live snapshot available';
  }, [datasetMode, datasetSource, effectiveSnapshotGeneratedAt, liveReason, snapshotRelative]);
  const snapshotTone = useMemo(() => {
    if (datasetMode !== 'live') {
      if (!effectiveSnapshotGeneratedAt) {
        return 'demo';
      }
      return snapshotIsStale ? 'stale' : 'demo';
    }
    if (datasetSource === 'meta_direct') {
      return snapshotIsStale ? 'stale' : 'fresh';
    }
    if (liveReason === 'adapter_disabled') {
      return 'warning';
    }
    if (liveReason === 'missing_snapshot') {
      return 'pending';
    }
    if (liveReason === 'stale_snapshot') {
      return 'stale';
    }
    if (liveReason === 'default_snapshot') {
      return 'warning';
    }
    if (!effectiveSnapshotGeneratedAt) {
      return 'pending';
    }
    return snapshotIsStale ? 'stale' : 'fresh';
  }, [datasetMode, datasetSource, effectiveSnapshotGeneratedAt, liveReason, snapshotIsStale]);
  const snapshotAbsolute = useMemo(
    () => formatAbsoluteTime(effectiveSnapshotGeneratedAt),
    [effectiveSnapshotGeneratedAt],
  );

  return (
    <div className="dashboard-shell" ref={shellRef}>
      <div className={`dashboard-top${isScrolled ? ' shadow' : ''}`} ref={dashboardTopRef}>
        <header className="dashboard-header">
          <div className="dashboard-boundary dashboard-header__inner">
            <div className="dashboard-header__brand">
              <p className="dashboard-header__title">ADinsights</p>
              <p className="muted">
                Active tenant <strong>{activeTenantLabel ?? tenantId ?? 'Select a tenant'}</strong>
                {selectedParish ? (
                  <span>
                    {' • '}Filtering to <strong>{selectedParish}</strong>
                  </span>
                ) : null}
              </p>
            </div>
            <div className="dashboard-header__actions">
              <div className="dashboard-header__meta">
                <TenantSwitcher />
                <DatasetToggle />
                <SnapshotIndicator
                  label={snapshotStatusLabel}
                  tone={snapshotTone}
                  timestamp={snapshotAbsolute}
                />
              </div>
              <div
                className="dashboard-header__controls"
                role="toolbar"
                aria-label="Dashboard quick actions"
              >
                <label htmlFor="metric-select" className="dashboard-field">
                  <span className="dashboard-field__label">Map metric</span>
                  <select
                    id="metric-select"
                    value={selectedMetric}
                    onChange={(event) =>
                      setSelectedMetric(event.target.value as typeof selectedMetric)
                    }
                  >
                    {metricOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  className="button tertiary theme-toggle"
                  onClick={toggleTheme}
                  aria-pressed={theme === 'dark'}
                >
                  <span className="theme-toggle__icon" aria-hidden="true">
                    {theme === 'dark' ? '🌞' : '🌙'}
                  </span>
                  <span>{theme === 'dark' ? 'Light' : 'Dark'} mode</span>
                </button>
                <div className="dashboard-header__divider" role="presentation" />
                <div
                  className="dashboard-header__actions-row"
                  role="group"
                  aria-label="Layout actions"
                >
                  <Link
                    className="button tertiary"
                    to="/dashboards/data-sources?sources=social"
                  >
                    Connect socials
                  </Link>
                  <button type="button" className="button secondary" onClick={handleSaveLayout}>
                    {SaveIcon}
                    Save layout
                  </button>
                  <button
                    type="button"
                    className="button secondary"
                    onClick={() => void handleCopyLink()}
                  >
                    {LinkIcon}
                    Copy link
                  </button>
                </div>
                <div
                  className="dashboard-header__account"
                  role="group"
                  aria-label="Account actions"
                >
                  <span className="muted user-pill">{accountLabel}</span>
                  <button type="button" className="button tertiary" onClick={logout}>
                    Log out
                  </button>
                </div>
              </div>
            </div>
          </div>
        </header>
        <nav className="dashboard-nav" aria-label="Dashboard sections">
          <div className="dashboard-boundary dashboard-nav__inner">
            <NavLink
              to="/"
              end
              className={({ isActive }: NavLinkRenderProps) => (isActive ? 'active' : undefined)}
            >
              Home
            </NavLink>
            {navGroups.map((group) => (
              <div key={group.label} className="dashboard-nav__group">
                <span className="dashboard-nav__group-label">{group.label}</span>
                {group.links.map((link) => (
                  <NavLink
                    key={link.to}
                    to={link.to}
                    end={link.end}
                    className={({ isActive }: NavLinkRenderProps) => (isActive ? 'active' : undefined)}
                  >
                    {link.label}
                  </NavLink>
                ))}
              </div>
            ))}
          </div>
        </nav>
        <div className="dashboard-boundary">
          <Breadcrumbs items={breadcrumbs} />
        </div>
      </div>
      {location.pathname === '/dashboards' || hideGlobalFilters ? null : (
        <FilterBar
          state={filters}
          defaultState={defaultFilters}
          availableAccounts={hasLiveData ? accountOptions : []}
          onChange={handleFilterChange}
        />
      )}
      {datasetMode === 'dummy' ? (
        <div className="dashboard-status">
          <div className="dashboard-boundary">
            <StatusBanner
              message="Demo dataset is active. Toggle to view live client data."
              ariaLabel="Dataset status"
            />
          </div>
        </div>
      ) : null}
      {datasetMode === 'live' && liveReason && liveReason !== 'ready' ? (
        <div className="dashboard-status">
          <div className="dashboard-boundary">
            <StatusBanner
              tone={
                datasetSource === 'meta_direct'
                  ? 'warning'
                  : liveReason === 'default_snapshot'
                    ? 'error'
                    : 'warning'
              }
              message={liveStatusMessage ?? 'Live data is unavailable.'}
              ariaLabel="Live data status"
            />
          </div>
        </div>
      ) : null}
      {errors.length > 0 ? (
        <div className="dashboard-status">
          <div className="dashboard-boundary">
            <StatusBanner
              tone="error"
              message={errors.map((message, index) => (
                <span key={`${message}-${index}`}>{message}</span>
              ))}
              ariaLabel="Dashboard errors"
            />
          </div>
        </div>
      ) : null}
      <main className="dashboard-content">
        <div className="dashboard-boundary">
          <Outlet />
        </div>
      </main>
    </div>
  );
};

export default DashboardLayout;
