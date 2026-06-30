import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import DashboardState from '../components/DashboardState';
import FilterBar, { type FilterBarAccountOption } from '../components/FilterBar';
import { loadSocialConnectionStatus, type SocialPlatformStatusRecord } from '../lib/airbyte';
import {
  buildLiveAccountOption,
  chooseDefaultLiveAccountOptionId,
  setLastLiveAccountId,
  sortLiveAccountOptions,
} from '../lib/liveAccountSelection';
import { KpiTile } from '../components/viz';
import { fetchDashboardMetrics } from '../lib/dataService';
import { messageForLiveDatasetReason } from '../lib/datasetStatus';
import {
  buildFilterQueryParams,
  createDefaultFilterState,
  parseFilterQueryParams,
  type FilterBarState,
} from '../lib/dashboardFilters';
import { getDashboardTemplate, DASHBOARD_TEMPLATES } from '../lib/dashboardTemplates';
import { formatNumber } from '../lib/format';
import { loadMetaAccounts } from '../lib/meta';
import {
  createDashboardDefinition,
  fetchReportingCatalog,
  previewDashboardWidget,
  type DashboardV1Widget,
  type DashboardMetricKey,
  type DashboardWidgetPreviewResponse,
  type ReportingCatalogMetric,
  type ReportingCatalogResponse,
  type DashboardTemplateKey,
} from '../lib/phase2Api';
import { canAccessCreatorUi } from '../lib/rbac';
import { useDatasetStore } from '../state/useDatasetStore';
import '../styles/dashboard.css';

type PreviewSummary = {
  currency: string;
  totalSpend: number;
  totalReach: number;
  totalClicks: number;
  averageRoas: number;
  ctr: number;
  campaignCount: number;
  creativeCount: number;
  budgetCount: number;
  coverageLabel?: string;
  availabilityReasons: string[];
};

type PreviewState =
  | { status: 'idle' | 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; summary: PreviewSummary };

type CatalogState =
  | { status: 'idle' | 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; catalog: ReportingCatalogResponse };

type GovernedWidgetState = {
  dataset: string;
  widgetType: string;
  metric: string;
  dimension: string;
  rowLimit: number;
  coveragePolicy: string;
};

type GovernedPreviewState =
  | { status: 'idle' | 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; payload: DashboardWidgetPreviewResponse };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function resolveSnapshotSource(snapshot: Record<string, unknown>): Record<string, unknown> {
  for (const key of ['metrics', 'snapshot', 'data', 'results', 'payload']) {
    const candidate = snapshot[key];
    if (isRecord(candidate)) {
      return candidate;
    }
  }
  return snapshot;
}

function extractPreviewSummary(payload: Record<string, unknown>): PreviewSummary {
  const source = resolveSnapshotSource(payload);
  const campaign = isRecord(source.campaign) ? source.campaign : {};
  const summary = isRecord(campaign.summary) ? campaign.summary : {};
  const creative = Array.isArray(source.creative) ? source.creative : [];
  const budget = Array.isArray(source.budget) ? source.budget : [];
  const coverage = isRecord(source.coverage) ? source.coverage : {};
  const availability = isRecord(source.availability) ? source.availability : {};

  const availabilityReasons = Object.values(availability)
    .map((entry) => (isRecord(entry) && typeof entry.reason === 'string' ? entry.reason : null))
    .filter((reason): reason is string => Boolean(reason));

  const campaignRows = Array.isArray(campaign.rows) ? campaign.rows : [];
  const coverageStart =
    typeof coverage.startDate === 'string'
      ? coverage.startDate
      : typeof coverage.start_date === 'string'
        ? coverage.start_date
        : '';
  const coverageEnd =
    typeof coverage.endDate === 'string'
      ? coverage.endDate
      : typeof coverage.end_date === 'string'
        ? coverage.end_date
        : '';

  return {
    currency: typeof summary.currency === 'string' ? summary.currency : 'USD',
    totalSpend: Number(summary.totalSpend ?? 0),
    totalReach: Number(summary.totalReach ?? 0),
    totalClicks: Number(summary.totalClicks ?? 0),
    averageRoas: Number(summary.averageRoas ?? 0),
    ctr: Number(summary.ctr ?? 0),
    campaignCount: campaignRows.length,
    creativeCount: creative.length,
    budgetCount: budget.length,
    coverageLabel: coverageStart && coverageEnd ? `${coverageStart} to ${coverageEnd}` : undefined,
    availabilityReasons,
  };
}

function buildPreviewBlockedMessage(metaStatus: SocialPlatformStatusRecord | null): string {
  const reasonCode = metaStatus?.reason.code;
  if (reasonCode === 'missing_meta_credential') {
    return 'Connect Meta first to load ad accounts for dashboard preview.';
  }
  if (reasonCode === 'missing_ad_account_selection') {
    return 'Finish Meta setup and choose an ad account to preview this dashboard.';
  }
  if (reasonCode === 'orphaned_marketing_access') {
    return (
      metaStatus?.reason.message ??
      'Restore Meta marketing access to recover ad accounts for preview.'
    );
  }
  if (
    reasonCode === 'page_insights_permissions_missing' ||
    reasonCode === 'marketing_permissions_missing'
  ) {
    return (
      metaStatus?.reason.message ??
      'Reconnect Meta with the required permissions to restore ad account preview.'
    );
  }
  return 'No Meta ad accounts are available for dashboard preview yet.';
}

function labelForCatalogKey(value: string): string {
  return value
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function normalizeDateRange(filters: FilterBarState): Record<string, string> {
  if (filters.dateRange === 'custom') {
    return {
      date_range: 'custom',
      start_date: filters.customRange.start,
      end_date: filters.customRange.end,
    };
  }
  const mapped: Partial<Record<FilterBarState['dateRange'], string>> = {
    '7d': 'last_7d',
    '30d': 'last_30d',
    '90d': 'last_90d',
    mtd: 'mtd',
  };
  return { date_range: mapped[filters.dateRange] ?? 'last_30d' };
}

function sanitizeWidgetId(...parts: string[]): string {
  return parts
    .join('_')
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, '_')
    .replace(/^_+|_+$/g, '');
}

function buildGovernedWidget(
  state: GovernedWidgetState,
  filters: FilterBarState,
): DashboardV1Widget {
  const dimensions =
    state.widgetType === 'kpi'
      ? []
      : state.widgetType === 'line_chart'
        ? ['date']
        : [state.dimension].filter(Boolean);
  const visual: Record<string, unknown> = {
    title: labelForCatalogKey(`${state.dataset}_${state.metric}`),
    source_labels: true,
  };
  if (state.widgetType === 'data_table') {
    visual.row_limit = state.rowLimit;
  }
  return {
    id: sanitizeWidgetId(state.dataset, state.metric, state.widgetType),
    type: state.widgetType,
    dataset: state.dataset,
    metrics: [state.metric],
    dimensions,
    filters: normalizeDateRange(filters),
    coverage_policy: state.coveragePolicy,
    visual,
  };
}

function buildDashboardV1Layout(widget: DashboardV1Widget): Record<string, unknown> {
  return {
    schema_version: 'dashboard.v1',
    layout: {
      columns: 12,
      slots: [
        {
          id: `slot_${widget.id}`,
          widget_id: widget.id,
          cols: widget.type === 'kpi' ? 4 : 8,
          rows: widget.type === 'data_table' ? 3 : 2,
        },
      ],
    },
    widgets: [widget],
  };
}

function firstActiveDataset(catalog: ReportingCatalogResponse): string {
  return (
    catalog.datasets.find((dataset) => dataset.status === 'active_v1' && !dataset.is_future_gated)
      ?.key ?? 'paid_meta_ads'
  );
}

function allowedMetrics(
  catalog: ReportingCatalogResponse,
  dataset: string,
  widgetType: string,
): ReportingCatalogMetric[] {
  return catalog.metrics.filter(
    (metric) =>
      metric.dataset === dataset &&
      metric.widgets.includes(widgetType) &&
      !metric.is_future_gated &&
      (!metric.availability_state || metric.availability_state === 'available'),
  );
}

function allowedDimensions(
  catalog: ReportingCatalogResponse,
  metric: ReportingCatalogMetric | undefined,
  widgetType: string,
): string[] {
  if (!metric || widgetType === 'kpi') {
    return [];
  }
  if (widgetType === 'line_chart') {
    return metric.dimensions.filter((dimension) =>
      catalog.compatibility.time_dimensions.includes(dimension),
    );
  }
  return metric.dimensions.filter(
    (dimension) => !catalog.compatibility.time_dimensions.includes(dimension),
  );
}

const DashboardCreate = () => {
  const { user, tenantId } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const canCreate = canAccessCreatorUi(user);
  const datasetSource = useDatasetStore((state) => state.source);
  const liveReason = useDatasetStore((state) => state.liveReason);
  const liveDetail = useDatasetStore((state) => state.liveDetail);
  const searchParams = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const initialTemplateKey =
    (searchParams.get('template') as DashboardTemplateKey | null) ?? 'meta_campaign_performance';
  const defaultFilters = useMemo(
    () => parseFilterQueryParams(searchParams, createDefaultFilterState()),
    [searchParams],
  );

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [templateKey, setTemplateKey] = useState<DashboardTemplateKey>(initialTemplateKey);
  const [filters, setFilters] = useState<FilterBarState>({
    ...defaultFilters,
    channels: ['Meta Ads'],
    // FP-CREATE-01: scope preview fetch to meta_ads only to match the Meta-only builder intent.
    platforms: ['meta_ads'],
  });
  const [defaultMetric, setDefaultMetric] = useState<DashboardMetricKey>(
    getDashboardTemplate(initialTemplateKey).defaultMetric,
  );
  const [selectedWidgets, setSelectedWidgets] = useState<string[]>(
    getDashboardTemplate(initialTemplateKey).widgets.map((widget) => widget.id),
  );
  const [accountOptions, setAccountOptions] = useState<FilterBarAccountOption[]>([]);
  const [accountOptionsStatus, setAccountOptionsStatus] = useState<'loading' | 'loaded' | 'error'>(
    'loading',
  );
  const [accountOptionsError, setAccountOptionsError] = useState<string>();
  const [metaStatus, setMetaStatus] = useState<SocialPlatformStatusRecord | null>(null);
  const [metaStatusResolved, setMetaStatusResolved] = useState(false);
  const [preview, setPreview] = useState<PreviewState>({ status: 'idle' });
  const [catalogState, setCatalogState] = useState<CatalogState>({ status: 'idle' });
  const [governedWidget, setGovernedWidget] = useState<GovernedWidgetState>({
    dataset: 'paid_meta_ads',
    widgetType: 'kpi',
    metric: 'spend',
    dimension: 'campaign',
    rowLimit: 25,
    coveragePolicy: 'render_with_warning',
  });
  const [governedPreview, setGovernedPreview] = useState<GovernedPreviewState>({
    status: 'idle',
  });
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'error'>('idle');
  const [saveError, setSaveError] = useState<string>();

  const selectedTemplate = useMemo(() => getDashboardTemplate(templateKey), [templateKey]);
  const catalog = catalogState.status === 'ready' ? catalogState.catalog : null;
  const activeWidget = useMemo(
    () => buildGovernedWidget(governedWidget, filters),
    [filters, governedWidget],
  );
  const metricOptions = useMemo(
    () =>
      catalog ? allowedMetrics(catalog, governedWidget.dataset, governedWidget.widgetType) : [],
    [catalog, governedWidget.dataset, governedWidget.widgetType],
  );
  const selectedCatalogMetric = metricOptions.find(
    (metric) => metric.key === governedWidget.metric,
  );
  const dimensionOptions = useMemo(
    () =>
      catalog ? allowedDimensions(catalog, selectedCatalogMetric, governedWidget.widgetType) : [],
    [catalog, governedWidget.widgetType, selectedCatalogMetric],
  );

  useEffect(() => {
    setDefaultMetric(selectedTemplate.defaultMetric);
    setSelectedWidgets(selectedTemplate.widgets.map((widget) => widget.id));
  }, [selectedTemplate]);

  useEffect(() => {
    const controller = new AbortController();
    setCatalogState({ status: 'loading' });
    void fetchReportingCatalog(controller.signal)
      .then((payload) => {
        const dataset = firstActiveDataset(payload);
        const widgetType =
          payload.widgets.find((widget) => widget.key === 'kpi' && !widget.is_future_gated)?.key ??
          'kpi';
        const metric = allowedMetrics(payload, dataset, widgetType)[0]?.key ?? 'spend';
        const metricDefinition = allowedMetrics(payload, dataset, widgetType).find(
          (item) => item.key === metric,
        );
        const dimension = allowedDimensions(payload, metricDefinition, widgetType)[0] ?? 'campaign';
        setCatalogState({ status: 'ready', catalog: payload });
        setGovernedWidget((previous) => ({
          ...previous,
          dataset,
          widgetType,
          metric,
          dimension,
          coveragePolicy: payload.coverage_policies.includes(previous.coveragePolicy)
            ? previous.coveragePolicy
            : 'render_with_warning',
        }));
      })
      .catch((error) => {
        if (controller.signal.aborted) {
          return;
        }
        setCatalogState({
          status: 'error',
          message: error instanceof Error ? error.message : 'Unable to load reporting catalog.',
        });
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!catalog) {
      return;
    }
    const nextMetrics = allowedMetrics(catalog, governedWidget.dataset, governedWidget.widgetType);
    const metric = nextMetrics.some((item) => item.key === governedWidget.metric)
      ? governedWidget.metric
      : nextMetrics[0]?.key;
    const metricDefinition = nextMetrics.find((item) => item.key === metric);
    const nextDimensions = allowedDimensions(catalog, metricDefinition, governedWidget.widgetType);
    const dimension = nextDimensions.includes(governedWidget.dimension)
      ? governedWidget.dimension
      : (nextDimensions[0] ?? '');
    if (metric && (metric !== governedWidget.metric || dimension !== governedWidget.dimension)) {
      setGovernedWidget((previous) => ({
        ...previous,
        metric,
        dimension,
      }));
    }
  }, [
    catalog,
    governedWidget.dataset,
    governedWidget.dimension,
    governedWidget.metric,
    governedWidget.widgetType,
  ]);

  useEffect(() => {
    let cancelled = false;
    setAccountOptionsStatus('loading');
    setAccountOptionsError(undefined);
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
        setAccountOptionsStatus('loaded');
      })
      .catch((error) => {
        console.warn('Failed to load Meta account options for dashboard builder', error);
        if (!cancelled) {
          setAccountOptions([]);
          setAccountOptionsStatus('error');
          setAccountOptionsError(
            error instanceof Error ? error.message : 'Unable to load Meta ad accounts.',
          );
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

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
    if (!tenantId || !metaStatusResolved || accountOptions.length === 0) {
      return;
    }
    const currentAccountId = filters.accountId.trim();
    const validAccountIds = accountOptions.map((option) => option.value);
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
    setFilters((previous) => ({
      ...previous,
      accountId: defaultAccountId,
    }));
  }, [accountOptions, filters.accountId, metaStatus, metaStatusResolved, tenantId]);

  useEffect(() => {
    if (!tenantId) {
      setPreview({ status: 'idle' });
      return;
    }

    if (!datasetSource || datasetSource === 'demo' || datasetSource === 'fake') {
      setPreview({
        status: 'error',
        message:
          datasetSource === 'demo' || datasetSource === 'fake'
            ? 'Switch back to live data to preview a dashboard with connected Meta accounts.'
            : messageForLiveDatasetReason('adapter_disabled', liveDetail),
      });
      return;
    }

    if (accountOptionsStatus === 'loading') {
      setPreview({ status: 'loading' });
      return;
    }

    if (accountOptionsStatus === 'error') {
      setPreview({
        status: 'error',
        message: accountOptionsError ?? 'Unable to load Meta ad accounts for preview.',
      });
      return;
    }

    if (!metaStatusResolved) {
      setPreview({ status: 'loading' });
      return;
    }

    if (accountOptions.length === 0) {
      setPreview({
        status: 'error',
        message: buildPreviewBlockedMessage(metaStatus),
      });
      return;
    }

    if (!filters.accountId.trim()) {
      setPreview({ status: 'loading' });
      return;
    }

    if (datasetSource === 'warehouse' && liveReason && liveReason !== 'ready') {
      setPreview({
        status: 'error',
        message: messageForLiveDatasetReason(liveReason, liveDetail),
      });
      return;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setPreview({ status: 'loading' });
      const query = new URLSearchParams({
        source: datasetSource,
        tenant_id: tenantId,
        ...buildFilterQueryParams(filters),
      });
      void fetchDashboardMetrics({
        path: `/metrics/combined/?${query.toString()}`,
        mockPath: '/sample_metrics.json',
        signal: controller.signal,
      })
        .then((snapshot) => {
          if (controller.signal.aborted) {
            return;
          }
          setPreview({
            status: 'ready',
            summary: extractPreviewSummary(snapshot as Record<string, unknown>),
          });
        })
        .catch((error) => {
          if (controller.signal.aborted) {
            return;
          }
          setPreview({
            status: 'error',
            message: error instanceof Error ? error.message : 'Unable to preview live data.',
          });
        });
    }, 250);

    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [
    accountOptions.length,
    accountOptionsError,
    accountOptionsStatus,
    filters,
    liveDetail,
    liveReason,
    metaStatus,
    metaStatusResolved,
    tenantId,
    datasetSource,
  ]);

  useEffect(() => {
    if (!catalog) {
      setGovernedPreview({ status: 'idle' });
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setGovernedPreview({ status: 'loading' });
      void previewDashboardWidget(
        {
          widget: activeWidget,
          date_range: normalizeDateRange(filters),
          account_id: filters.accountId.trim() || undefined,
          client_id: filters.clientId.trim() || undefined,
        },
        controller.signal,
      )
        .then((payload) => {
          if (!controller.signal.aborted) {
            setGovernedPreview({ status: 'ready', payload });
          }
        })
        .catch((error) => {
          if (controller.signal.aborted) {
            return;
          }
          setGovernedPreview({
            status: 'error',
            message: error instanceof Error ? error.message : 'Unable to preview governed widget.',
          });
        });
    }, 250);

    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [activeWidget, catalog, filters]);

  const toggleWidget = useCallback((widgetId: string) => {
    setSelectedWidgets((current) =>
      current.includes(widgetId)
        ? current.filter((item) => item !== widgetId)
        : [...current, widgetId],
    );
  }, []);

  const handleSave = useCallback(async () => {
    if (!name.trim()) {
      setSaveState('error');
      setSaveError('Dashboard name is required.');
      return;
    }
    if (!filters.accountId.trim()) {
      setSaveState('error');
      setSaveError('Select a Meta client account before saving.');
      return;
    }

    setSaveState('saving');
    setSaveError(undefined);
    try {
      const created = await createDashboardDefinition({
        name: name.trim(),
        description: description.trim(),
        template_key: templateKey,
        filters: {
          ...filters,
          channels: ['Meta Ads'],
        },
        layout: buildDashboardV1Layout(activeWidget),
        default_metric: defaultMetric,
        is_active: true,
      });
      navigate(`/dashboards/saved/${created.id}`);
    } catch (error) {
      setSaveState('error');
      setSaveError(error instanceof Error ? error.message : 'Unable to save dashboard.');
    }
  }, [defaultMetric, description, filters, name, navigate, templateKey, activeWidget]);

  if (!canCreate) {
    return (
      <DashboardState
        variant="empty"
        layout="page"
        title="Read-only dashboard access"
        message="Viewer access can browse dashboards, but cannot create new ones."
        actionLabel="Back to library"
        onAction={() => navigate('/dashboards')}
      />
    );
  }

  return (
    <div className="dashboardGrid">
      <section className="panel full-width">
        <header className="panel-header">
          <div className="panel-header__title-row">
            <div>
              <p className="dashboardEyebrow">Dashboard builder</p>
              <h2>Create a saved Meta dashboard</h2>
            </div>
          </div>
          <p className="muted">
            Choose the client account, template, and default window. This saves a real dashboard
            definition, not just a local layout preference.
          </p>
        </header>

        <div className="dashboard-builder__grid">
          <label className="library-field">
            <span className="library-field__label">Dashboard name</span>
            <input
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="SLB weekly executive overview"
            />
          </label>

          <label className="library-field">
            <span className="library-field__label">Template</span>
            <select
              value={templateKey}
              onChange={(event) => setTemplateKey(event.target.value as DashboardTemplateKey)}
            >
              {DASHBOARD_TEMPLATES.map((template) => (
                <option key={template.key} value={template.key}>
                  {template.label}
                </option>
              ))}
            </select>
          </label>

          <label className="library-field dashboard-builder__field--wide">
            <span className="library-field__label">Description</span>
            <textarea
              rows={3}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder={selectedTemplate.subtitle}
            />
          </label>

          <label className="library-field">
            <span className="library-field__label">Default metric</span>
            <select
              value={defaultMetric}
              onChange={(event) => setDefaultMetric(event.target.value as DashboardMetricKey)}
            >
              {[
                'spend',
                'impressions',
                'reach',
                'clicks',
                'ctr',
                'cpc',
                'cpm',
                'conversions',
                'cpa',
                'frequency',
                'roas',
              ].map((metric) => (
                <option key={metric} value={metric}>
                  {metric.toUpperCase()}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      <section className="panel full-width">
        <header className="panel-header">
          <div className="panel-header__title-row">
            <h2>Default filters</h2>
          </div>
          <p className="muted">
            These filters become the saved dashboard’s default live query for the selected Meta ad
            account.
          </p>
        </header>
        <FilterBar
          state={filters}
          defaultState={defaultFilters}
          availableAccounts={accountOptions}
          availableChannels={['Meta Ads']}
          onChange={(nextState) => {
            if (
              tenantId &&
              nextState.accountId.trim() &&
              nextState.accountId !== filters.accountId
            ) {
              setLastLiveAccountId(tenantId, nextState.accountId, 'user');
            }
            setFilters({
              ...nextState,
              channels: ['Meta Ads'],
            });
          }}
        />
      </section>

      <section className="panel full-width">
        <header className="panel-header">
          <div className="panel-header__title-row">
            <h2>Allowed widgets</h2>
          </div>
          <p className="muted">
            Saved dashboards use approved widget sets rather than freeform drag-and-drop.
          </p>
        </header>
        <div className="dashboard-builder__widgets">
          {selectedTemplate.widgets.map((widget) => {
            const checked = selectedWidgets.includes(widget.id);
            return (
              <label key={widget.id} className="dashboard-builder__widget">
                <input type="checkbox" checked={checked} onChange={() => toggleWidget(widget.id)} />
                <div>
                  <strong>{widget.label}</strong>
                  <p className="muted">{widget.description}</p>
                </div>
              </label>
            );
          })}
        </div>
      </section>

      <section className="panel full-width">
        <header className="panel-header">
          <div className="panel-header__title-row">
            <h2>Governed reporting widget</h2>
          </div>
          <p className="muted">
            These options come from the backend reporting catalog and save as a dashboard.v1 widget.
          </p>
        </header>

        {catalogState.status === 'loading' || catalogState.status === 'idle' ? (
          <DashboardState
            variant="loading"
            layout="compact"
            message="Loading reporting catalog..."
          />
        ) : null}

        {catalogState.status === 'error' ? (
          <DashboardState
            variant="error"
            layout="compact"
            title="Catalog unavailable"
            message={catalogState.message}
          />
        ) : null}

        {catalog ? (
          <>
            <div className="dashboard-builder__grid">
              <label className="library-field">
                <span className="library-field__label">Dataset</span>
                <select
                  value={governedWidget.dataset}
                  onChange={(event) =>
                    setGovernedWidget((previous) => ({
                      ...previous,
                      dataset: event.target.value,
                    }))
                  }
                >
                  {catalog.datasets
                    .filter((dataset) => dataset.status === 'active_v1' && !dataset.is_future_gated)
                    .map((dataset) => (
                      <option key={dataset.key} value={dataset.key}>
                        {labelForCatalogKey(dataset.key)}
                      </option>
                    ))}
                </select>
              </label>

              <label className="library-field">
                <span className="library-field__label">Widget type</span>
                <select
                  value={governedWidget.widgetType}
                  onChange={(event) =>
                    setGovernedWidget((previous) => ({
                      ...previous,
                      widgetType: event.target.value,
                    }))
                  }
                >
                  {catalog.widgets
                    .filter((widget) =>
                      ['kpi', 'line_chart', 'bar_chart', 'data_table'].includes(widget.key),
                    )
                    .filter((widget) => !widget.is_future_gated)
                    .map((widget) => (
                      <option key={widget.key} value={widget.key}>
                        {labelForCatalogKey(widget.key)}
                      </option>
                    ))}
                </select>
              </label>

              <label className="library-field">
                <span className="library-field__label">Metric</span>
                <select
                  value={governedWidget.metric}
                  onChange={(event) =>
                    setGovernedWidget((previous) => ({
                      ...previous,
                      metric: event.target.value,
                    }))
                  }
                >
                  {metricOptions.map((metric) => (
                    <option key={`${metric.dataset}.${metric.key}`} value={metric.key}>
                      {labelForCatalogKey(metric.key)}
                    </option>
                  ))}
                </select>
              </label>

              {governedWidget.widgetType !== 'kpi' ? (
                <label className="library-field">
                  <span className="library-field__label">X dimension</span>
                  <select
                    value={governedWidget.dimension}
                    onChange={(event) =>
                      setGovernedWidget((previous) => ({
                        ...previous,
                        dimension: event.target.value,
                      }))
                    }
                  >
                    {dimensionOptions.map((dimension) => (
                      <option key={dimension} value={dimension}>
                        {labelForCatalogKey(dimension)}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}

              {governedWidget.widgetType === 'data_table' ? (
                <label className="library-field">
                  <span className="library-field__label">Row limit</span>
                  <input
                    type="number"
                    min={1}
                    max={catalog.compatibility.table.max_row_limit}
                    value={governedWidget.rowLimit}
                    onChange={(event) =>
                      setGovernedWidget((previous) => ({
                        ...previous,
                        rowLimit: Number(event.target.value),
                      }))
                    }
                  />
                </label>
              ) : null}

              <label className="library-field">
                <span className="library-field__label">Coverage policy</span>
                <select
                  value={governedWidget.coveragePolicy}
                  onChange={(event) =>
                    setGovernedWidget((previous) => ({
                      ...previous,
                      coveragePolicy: event.target.value,
                    }))
                  }
                >
                  {catalog.coverage_policies.map((policy) => (
                    <option key={policy} value={policy}>
                      {labelForCatalogKey(policy)}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="dashboard-builder__preview-meta">
              {governedPreview.status === 'idle' || governedPreview.status === 'loading' ? (
                <p>
                  <strong>Governed preview:</strong> Loading widget preview...
                </p>
              ) : null}
              {governedPreview.status === 'error' ? (
                <p className="status-message error">{governedPreview.message}</p>
              ) : null}
              {governedPreview.status === 'ready' ? (
                <>
                  <p>
                    <strong>Governed preview:</strong>{' '}
                    {labelForCatalogKey(governedPreview.payload.type)} from{' '}
                    {labelForCatalogKey(governedPreview.payload.dataset)}
                  </p>
                  <p>
                    <strong>Coverage state:</strong>{' '}
                    {governedPreview.payload.coverage
                      ? labelForCatalogKey(governedPreview.payload.coverage.coverage_status)
                      : 'Unavailable'}
                  </p>
                  <p>
                    <strong>Coverage note:</strong>{' '}
                    {governedPreview.payload.coverage?.coverage_note ??
                      'Coverage was not returned for this preview.'}
                  </p>
                </>
              ) : null}
            </div>
          </>
        ) : null}
      </section>

      <section className="panel full-width">
        <header className="panel-header">
          <div className="panel-header__title-row">
            <h2>Live preview</h2>
          </div>
          <p className="muted">
            Preview is pulled from the same live combined endpoint the dashboards use.
            {datasetSource === 'meta_direct'
              ? ' In this environment that currently means direct Meta sync data rather than warehouse output.'
              : null}
          </p>
        </header>

        {preview.status === 'idle' ? (
          <DashboardState
            variant="empty"
            layout="compact"
            title="Pick a Meta account to preview"
            message="Choose a connected Meta ad account above to preview live client data. Facebook Pages stay on the Facebook pages route."
          />
        ) : null}

        {preview.status === 'loading' ? (
          <DashboardState
            variant="loading"
            layout="compact"
            message="Loading live Meta preview..."
          />
        ) : null}

        {preview.status === 'error' ? (
          <DashboardState
            variant="error"
            layout="compact"
            title="Preview unavailable"
            message={preview.message}
          />
        ) : null}

        {preview.status === 'ready' ? (
          <div className="dashboard-builder__preview">
            {/* S4c: migrated builder preview to shared viz-kit `KpiTile`
                (replaces 5 legacy `StatCard` tiles at the former lines
                593–598). `KpiTile` renders the same `.metric-card` DOM
                class so existing Storybook a11y assertions and CSS layouts
                remain stable; FP-CREATE-01 `platforms: ['meta_ads']` default
                on the preview fetch (configured above at the filters
                setState) is unchanged. */}
            <div className="kpiColumn" role="group" aria-label="Live preview KPIs">
              <KpiTile
                label="Spend"
                value={preview.summary.totalSpend}
                format="currency"
                currency={preview.summary.currency}
              />
              <KpiTile label="Reach" value={preview.summary.totalReach} format="number" />
              <KpiTile label="Clicks" value={preview.summary.totalClicks} format="number" />
              <KpiTile label="CTR" value={preview.summary.ctr} format="rate" />
              <KpiTile label="ROAS" value={preview.summary.averageRoas} format="rate" />
            </div>
            <div className="dashboard-builder__preview-meta">
              <p>
                <strong>Campaign rows:</strong> {formatNumber(preview.summary.campaignCount)}
              </p>
              <p>
                <strong>Creative rows:</strong> {formatNumber(preview.summary.creativeCount)}
              </p>
              <p>
                <strong>Budget rows:</strong> {formatNumber(preview.summary.budgetCount)}
              </p>
              <p>
                <strong>Coverage:</strong> {preview.summary.coverageLabel ?? 'Unavailable'}
              </p>
              {preview.summary.availabilityReasons.length > 0 ? (
                <p>
                  <strong>Availability notes:</strong>{' '}
                  {preview.summary.availabilityReasons.join(', ')}
                </p>
              ) : (
                <p>
                  <strong>Availability notes:</strong> All core sections are available for this
                  selection.
                </p>
              )}
            </div>
          </div>
        ) : null}
      </section>

      <section className="panel full-width">
        <div className="chart-card__actions">
          <button type="button" className="button tertiary" onClick={() => navigate('/dashboards')}>
            Back to library
          </button>
          <button
            type="button"
            className="button primary"
            onClick={() => void handleSave()}
            disabled={saveState === 'saving'}
          >
            {saveState === 'saving' ? 'Saving…' : 'Save dashboard'}
          </button>
        </div>
        {saveError ? <p className="status-message error">{saveError}</p> : null}
      </section>
    </div>
  );
};

export default DashboardCreate;
