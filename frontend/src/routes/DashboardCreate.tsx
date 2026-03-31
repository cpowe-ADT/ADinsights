import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import DashboardState from '../components/DashboardState';
import FilterBar, { type FilterBarAccountOption } from '../components/FilterBar';
import StatCard from '../components/ui/StatCard';
import { fetchDashboardMetrics } from '../lib/dataService';
import {
  buildFilterQueryParams,
  createDefaultFilterState,
  parseFilterQueryParams,
  type FilterBarState,
} from '../lib/dashboardFilters';
import { getDashboardTemplate, DASHBOARD_TEMPLATES } from '../lib/dashboardTemplates';
import { formatCurrency, formatNumber, formatRatio } from '../lib/format';
import { loadMetaAccounts } from '../lib/meta';
import { createDashboardDefinition, type DashboardMetricKey, type DashboardTemplateKey } from '../lib/phase2Api';
import { canAccessCreatorUi } from '../lib/rbac';
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

const DashboardCreate = () => {
  const { user, tenantId } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const canCreate = canAccessCreatorUi(user);
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
  });
  const [defaultMetric, setDefaultMetric] = useState<DashboardMetricKey>(
    getDashboardTemplate(initialTemplateKey).defaultMetric,
  );
  const [selectedWidgets, setSelectedWidgets] = useState<string[]>(
    getDashboardTemplate(initialTemplateKey).widgets.map((widget) => widget.id),
  );
  const [accountOptions, setAccountOptions] = useState<FilterBarAccountOption[]>([]);
  const [preview, setPreview] = useState<PreviewState>({ status: 'idle' });
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'error'>('idle');
  const [saveError, setSaveError] = useState<string>();

  const selectedTemplate = useMemo(() => getDashboardTemplate(templateKey), [templateKey]);

  useEffect(() => {
    setDefaultMetric(selectedTemplate.defaultMetric);
    setSelectedWidgets(selectedTemplate.widgets.map((widget) => widget.id));
  }, [selectedTemplate]);

  useEffect(() => {
    let cancelled = false;
    void loadMetaAccounts({ page_size: 200 })
      .then((payload) => {
        if (cancelled) {
          return;
        }
        const options = payload.results
          .map((account) => {
            const value = account.external_id?.trim() || account.account_id?.trim() || '';
            if (!value) {
              return null;
            }
            return {
              value,
              label: [account.name?.trim(), account.account_id?.trim() || account.external_id]
                .filter(Boolean)
                .join(' · '),
            };
          })
          .filter((option): option is FilterBarAccountOption => option !== null);
        setAccountOptions(options);
      })
      .catch((error) => {
        console.warn('Failed to load Meta account options for dashboard builder', error);
        if (!cancelled) {
          setAccountOptions([]);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!filters.accountId.trim() || !tenantId) {
      setPreview({ status: 'idle' });
      return;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setPreview({ status: 'loading' });
      const query = new URLSearchParams({
        source: 'warehouse',
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
  }, [filters, tenantId]);

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
        layout: {
          routeKind: selectedTemplate.routeKind,
          widgets: selectedWidgets,
        },
        default_metric: defaultMetric,
        is_active: true,
      });
      navigate(`/dashboards/saved/${created.id}`);
    } catch (error) {
      setSaveState('error');
      setSaveError(error instanceof Error ? error.message : 'Unable to save dashboard.');
    }
  }, [defaultMetric, description, filters, name, navigate, selectedTemplate.routeKind, selectedWidgets, templateKey]);

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
            Choose the client account, template, and default window. This saves a real dashboard definition, not just a local layout preference.
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
          <p className="muted">These filters become the saved dashboard’s default warehouse query.</p>
        </header>
        <FilterBar
          state={filters}
          defaultState={defaultFilters}
          availableAccounts={accountOptions}
          availableChannels={['Meta Ads']}
          onChange={(nextState) =>
            setFilters({
              ...nextState,
              channels: ['Meta Ads'],
            })
          }
        />
      </section>

      <section className="panel full-width">
        <header className="panel-header">
          <div className="panel-header__title-row">
            <h2>Allowed widgets</h2>
          </div>
          <p className="muted">Saved dashboards use approved widget sets rather than freeform drag-and-drop.</p>
        </header>
        <div className="dashboard-builder__widgets">
          {selectedTemplate.widgets.map((widget) => {
            const checked = selectedWidgets.includes(widget.id);
            return (
              <label key={widget.id} className="dashboard-builder__widget">
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggleWidget(widget.id)}
                />
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
            <h2>Live preview</h2>
          </div>
          <p className="muted">Preview is pulled from the same warehouse combined endpoint the dashboards use.</p>
        </header>

        {preview.status === 'idle' ? (
          <DashboardState
            variant="empty"
            layout="compact"
            title="Pick a Meta account to preview"
            message="Choose a connected client account above to preview live warehouse data."
          />
        ) : null}

        {preview.status === 'loading' ? (
          <DashboardState variant="loading" layout="compact" message="Loading live Meta preview..." />
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
            <div className="kpiColumn">
              <StatCard label="Spend" value={formatCurrency(preview.summary.totalSpend, preview.summary.currency)} />
              <StatCard label="Reach" value={formatNumber(preview.summary.totalReach)} />
              <StatCard label="Clicks" value={formatNumber(preview.summary.totalClicks)} />
              <StatCard label="CTR" value={formatRatio(preview.summary.ctr, 2)} />
              <StatCard label="ROAS" value={formatRatio(preview.summary.averageRoas, 2)} />
            </div>
            <div className="dashboard-builder__preview-meta">
              <p><strong>Campaign rows:</strong> {formatNumber(preview.summary.campaignCount)}</p>
              <p><strong>Creative rows:</strong> {formatNumber(preview.summary.creativeCount)}</p>
              <p><strong>Budget rows:</strong> {formatNumber(preview.summary.budgetCount)}</p>
              <p><strong>Coverage:</strong> {preview.summary.coverageLabel ?? 'Unavailable'}</p>
              {preview.summary.availabilityReasons.length > 0 ? (
                <p><strong>Availability notes:</strong> {preview.summary.availabilityReasons.join(', ')}</p>
              ) : (
                <p><strong>Availability notes:</strong> All core sections are available for this selection.</p>
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
          <button type="button" className="button primary" onClick={() => void handleSave()} disabled={saveState === 'saving'}>
            {saveState === 'saving' ? 'Saving…' : 'Save dashboard'}
          </button>
        </div>
        {saveError ? <p className="status-message error">{saveError}</p> : null}
      </section>
    </div>
  );
};

export default DashboardCreate;
