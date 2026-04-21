import { useEffect, useMemo, useRef, useState } from 'react';
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
import {
  getDashboardTemplate,
  type DashboardTemplateDefinition,
  type SlotConfig,
} from '../lib/dashboardTemplates';
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
    clientId: typeof value.clientId === 'string' ? value.clientId : fallback.clientId,
    channels: Array.isArray(value.channels)
      ? value.channels.map((entry) => String(entry))
      : fallback.channels,
    // FP-SAVED-01: restore platforms so a saved meta_ads-only dashboard does not silently widen scope.
    platforms: Array.isArray(value.platforms)
      ? value.platforms.map((entry) => String(entry))
      : fallback.platforms,
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

/**
 * S4c grid-snap extension — slot-grid renderer.
 *
 * Sprint 4 does NOT populate `template.layout.slots` for any shipped template;
 * the full-page `renderTemplate` path remains the single source of truth and
 * FP-SAVED-01/02 are untouched. When a future sprint adds slots, this grid
 * takes over: each slot is a named 12-column region, accessible via
 * `role="region"` + `aria-label`, and rendered by a `kind`-specific body.
 * Sprint 5+ can extend `SlotBody` to compose shared viz-kit primitives
 * (`KpiTile`, `TrendLine`, `VizDataTable`, etc.) without touching this file.
 */
const SlotBody = ({ slot }: { slot: SlotConfig }) => {
  return (
    <div className="saved-dashboard-slot__body" data-slot-kind={slot.kind}>
      <p className="muted">
        Slot &quot;{slot.kind}&quot; — renderer pending.
      </p>
    </div>
  );
};

const SavedDashboardSlotGrid = ({ slots }: { slots: SlotConfig[] }) => {
  return (
    <div className="saved-dashboard-slot-grid">
      {slots.map((slot) => {
        const cols = Math.max(1, Math.min(12, slot.cols));
        const rows = Math.max(1, Math.min(6, slot.rows));
        return (
          <section
            key={slot.id}
            className="saved-dashboard-slot"
            role="region"
            aria-label={slot.title ?? slot.id}
            style={{ gridColumn: `span ${cols}`, gridRow: `span ${rows}` }}
          >
            {slot.title ? <h3 className="saved-dashboard-slot__title">{slot.title}</h3> : null}
            <SlotBody slot={slot} />
          </section>
        );
      })}
    </div>
  );
};

function renderTemplateBody(
  template: DashboardTemplateDefinition,
  templateKey: DashboardDefinition['template_key'],
) {
  // S4c: if the template carries optional slot layout metadata, hand off to
  // the grid renderer; otherwise preserve the legacy full-page dispatch so
  // every shipped Sprint-4 template (all four route-kinds) renders exactly
  // as it did pre-S4. This path is backward-compatible by construction.
  if (template.layout?.slots?.length) {
    return <SavedDashboardSlotGrid slots={template.layout.slots} />;
  }
  return renderTemplate(templateKey);
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

  // FP-SAVED-02: track whether we have already seeded the store from the saved definition,
  // so that subsequent URL changes (driven by DashboardLayout's filter→URL sync) do not
  // re-trigger setFilters and lock the user's filter edits to the saved values.
  const seededRef = useRef(false);
  // Reset the ref whenever the dashboardId param changes (user navigates to a different saved dashboard).
  const prevDashboardIdRef = useRef(dashboardId);
  if (prevDashboardIdRef.current !== dashboardId) {
    prevDashboardIdRef.current = dashboardId;
    seededRef.current = false;
  }

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
    if (!dashboard || seededRef.current) {
      return;
    }
    // FP-SAVED-02: seed once; do not re-seed on URL changes driven by DashboardLayout.
    seededRef.current = true;
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
    // Intentionally omit location.search from deps — subsequent URL changes must NOT re-seed.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dashboard, location.pathname, navigate, setFilters, setSelectedMetric, setSelectedParish]);

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
      {renderTemplateBody(template, dashboard.template_key)}
    </div>
  );
};

export default SavedDashboardPage;
