import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';

import DashboardState from '../components/DashboardState';
import {
  getDashboardDefinition,
  type DashboardDefinition,
} from '../lib/phase2Api';
import {
  createDefaultFilterState,
  serializeFilterQueryParams,
  type FilterBarState,
} from '../lib/dashboardFilters';
import { getDashboardTemplate } from '../lib/dashboardTemplates';
import CampaignDashboard from './CampaignDashboard';
import CreativeDashboard from './CreativeDashboard';
import BudgetDashboard from './BudgetDashboard';
import ParishMapDetail from './ParishMapDetail';
import useDashboardStore, { type MetricKey } from '../state/useDashboardStore';

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function normalizeFilters(value: unknown): FilterBarState {
  const fallback = createDefaultFilterState();
  if (!isRecord(value)) {
    return fallback;
  }

  const customRange = isRecord(value.customRange)
    ? {
        start:
          typeof value.customRange.start === 'string'
            ? value.customRange.start
            : fallback.customRange.start,
        end:
          typeof value.customRange.end === 'string'
            ? value.customRange.end
            : fallback.customRange.end,
      }
    : fallback.customRange;

  return {
    dateRange:
      typeof value.dateRange === 'string'
        ? (value.dateRange as FilterBarState['dateRange'])
        : fallback.dateRange,
    customRange,
    accountId: typeof value.accountId === 'string' ? value.accountId : fallback.accountId,
    channels: Array.isArray(value.channels)
      ? value.channels.map((entry) => String(entry))
      : fallback.channels,
    campaignQuery:
      typeof value.campaignQuery === 'string' ? value.campaignQuery : fallback.campaignQuery,
  };
}

function renderTemplate(templateKey: DashboardDefinition['template_key']) {
  const template = getDashboardTemplate(templateKey);
  switch (template.routeKind) {
    case 'creatives':
      return <CreativeDashboard />;
    case 'budget':
      return <BudgetDashboard />;
    case 'map':
      return <ParishMapDetail />;
    case 'campaigns':
    default:
      return <CampaignDashboard />;
  }
}

const SavedDashboardPage = () => {
  const { dashboardId } = useParams<{ dashboardId: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [dashboard, setDashboard] = useState<DashboardDefinition | null>(null);
  const [error, setError] = useState<string>();

  const setFilters = useDashboardStore((state) => state.setFilters);
  const setSelectedMetric = useDashboardStore((state) => state.setSelectedMetric);
  const setSelectedParish = useDashboardStore((state) => state.setSelectedParish);

  useEffect(() => {
    if (!dashboardId) {
      setStatus('error');
      setError('Saved dashboard id is missing.');
      return;
    }

    const controller = new AbortController();
    setStatus('loading');
    setError(undefined);

    void getDashboardDefinition(dashboardId, controller.signal)
      .then((definition) => {
        setDashboard(definition);
        setStatus('ready');
      })
      .catch((loadError) => {
        if (controller.signal.aborted) {
          return;
        }
        setError(loadError instanceof Error ? loadError.message : 'Unable to load saved dashboard.');
        setStatus('error');
      });

    return () => controller.abort();
  }, [dashboardId]);

  useEffect(() => {
    if (!dashboard) {
      return;
    }
    const normalizedFilters = normalizeFilters(dashboard.filters);
    const nextSearch = serializeFilterQueryParams(normalizedFilters);
    const currentSearch = location.search.replace(/^\?/, '');
    if (nextSearch !== currentSearch) {
      navigate(
        {
          pathname: location.pathname,
          search: nextSearch ? `?${nextSearch}` : '',
        },
        { replace: true },
      );
    }
    setFilters(normalizedFilters);
    setSelectedMetric(dashboard.default_metric as MetricKey);
    setSelectedParish(undefined);
  }, [dashboard, location.pathname, location.search, navigate, setFilters, setSelectedMetric, setSelectedParish]);

  const template = useMemo(
    () => getDashboardTemplate(dashboard?.template_key),
    [dashboard?.template_key],
  );

  if (status === 'loading') {
    return <DashboardState variant="loading" layout="page" message="Loading saved dashboard..." />;
  }

  if (status === 'error' || !dashboard) {
    return (
      <DashboardState
        variant="error"
        layout="page"
        title="Saved dashboard unavailable"
        message={error ?? 'Unable to load the saved dashboard.'}
      />
    );
  }

  return (
    <div className="saved-dashboard">
      <section className="panel full-width saved-dashboard__header">
        <header className="panel-header">
          <div className="panel-header__title-row">
            <div>
              <p className="dashboardEyebrow">Saved dashboard</p>
              <h2>{dashboard.name}</h2>
            </div>
            <Link to="/dashboards" className="button tertiary">
              Back to library
            </Link>
          </div>
          <p className="muted">
            {dashboard.description || template.subtitle}
          </p>
        </header>
      </section>
      {renderTemplate(dashboard.template_key)}
    </div>
  );
};

export default SavedDashboardPage;
