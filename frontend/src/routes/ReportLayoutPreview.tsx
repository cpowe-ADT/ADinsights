import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent } from 'react';
import { Link, useParams } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import DashboardState from '../components/DashboardState';
import {
  GridCanvas,
  LayoutEditor,
  createStoreResolver,
  liveDashboardLayout,
  loadLayout,
  mergeGovernedWidgets,
  reportPreviewToLayout,
  reportingCatalogToWidgets,
  saveLayout,
  type DashboardLayoutConfig,
  type DashboardWidget,
} from '../components/report-layout';
import {
  deleteSavedLayout,
  listSavedLayouts,
  saveLayoutToApi,
  updateSavedLayout,
  type SavedReportLayout,
} from '../components/report-layout/savedReportLayouts';
import SkeletonLoader from '../components/SkeletonLoader';
import {
  fetchReportDataAvailability,
  fetchReportingCatalog,
  getReport,
  previewReport,
  type ReportDataAvailabilityResponse,
  type ReportDefinition,
  type ReportMetricAvailabilityEntry,
} from '../lib/phase2Api';
import useDashboardStore from '../state/useDashboardStore';

import '../styles/dashboard.css';
import '../styles/skeleton.css';

type ReportDataAvailabilityQuery = NonNullable<Parameters<typeof fetchReportDataAvailability>[0]>;

const availabilityQueryKeys = [
  'template_key',
  'date_range',
  'start_date',
  'end_date',
  'client_id',
  'account_id',
  'page_id',
] as const;

const stringQueryValue = (value: unknown): string | undefined => {
  if (typeof value !== 'string') return undefined;
  const trimmed = value.trim();
  return trimmed || undefined;
};

function reportAvailabilityQuery(report: ReportDefinition): ReportDataAvailabilityQuery {
  const filters = (report.filters ?? {}) as Record<string, unknown>;
  const layout = (report.layout ?? {}) as Record<string, unknown>;
  const query: ReportDataAvailabilityQuery = {};
  for (const key of availabilityQueryKeys) {
    const value = stringQueryValue(filters[key] ?? layout[key]);
    if (value) {
      query[key] = value;
    }
  }
  return query;
}

function availabilityDatasetForMetric(dataset: string | undefined, metric: string): string {
  if (dataset === 'organic_facebook_page' && metric.startsWith('post_')) {
    return 'organic_facebook_posts';
  }
  return dataset ?? '';
}

function metricAvailabilityIndex(
  availability: ReportDataAvailabilityResponse | null,
): Map<string, Map<string, ReportMetricAvailabilityEntry>> {
  const result = new Map<string, Map<string, ReportMetricAvailabilityEntry>>();
  if (!availability) return result;
  for (const [dataset, payload] of Object.entries(availability.datasets)) {
    const entries = payload.metric_availability?.metrics ?? [];
    result.set(dataset, new Map(entries.map((entry) => [entry.key, entry])));
  }
  return result;
}

function annotateLayoutAvailability(
  layout: DashboardLayoutConfig,
  availability: ReportDataAvailabilityResponse | null,
  sourceLayout?: DashboardLayoutConfig | null,
): DashboardLayoutConfig {
  const availabilityByDataset = metricAvailabilityIndex(availability);
  const sourceById = new Map((sourceLayout?.widgets ?? []).map((widget) => [widget.id, widget]));
  return {
    ...layout,
    widgets: layout.widgets.map((widget) => {
      const source = widget.source ?? sourceById.get(widget.id)?.source;
      const metrics = source?.metrics ?? [];
      if (!source || metrics.length === 0) {
        return source && source !== widget.source ? { ...widget, source } : widget;
      }
      const runtimeAvailability = metrics.flatMap((metric) => {
        const dataset = availabilityDatasetForMetric(source.dataset, metric);
        const entry = availabilityByDataset.get(dataset)?.get(metric);
        return entry
          ? [
              {
                key: metric,
                state: entry.availability_state,
                note: entry.availability_note,
                rowCount: entry.row_count,
              },
            ]
          : [];
      });
      return {
        ...widget,
        source: {
          ...source,
          availability: runtimeAvailability,
        },
      };
    }),
  };
}

/**
 * Config-driven report layout bound to live data. In `/dashboards/report-preview`
 * it remains the dashboard-store preview. In `/reports/:reportId/builder`, it
 * starts from the governed report preview endpoint, converts those widgets into
 * the shared layout config, and persists edits through `SavedReportLayoutViewSet`.
 */
const ReportLayoutPreview = () => {
  const { reportId } = useParams<{ reportId?: string }>();
  const isReportBuilder = Boolean(reportId);
  const { tenantId } = useAuth();
  const loadAll = useDashboardStore((state) => state.loadAll);
  const summary = useDashboardStore((state) => state.campaign.data?.summary ?? null);
  const parish = useDashboardStore((state) => state.parish.data ?? null);

  const [editing, setEditing] = useState(false);
  const [layout, setLayout] = useState<DashboardLayoutConfig>(
    () => loadLayout(liveDashboardLayout.id) ?? liveDashboardLayout,
  );
  const [sourceLayout, setSourceLayout] = useState<DashboardLayoutConfig | null>(null);
  const [report, setReport] = useState<ReportDefinition | null>(null);
  const [catalogSchemaVersion, setCatalogSchemaVersion] = useState<string | null>(null);
  const [dataAvailability, setDataAvailability] = useState<ReportDataAvailabilityResponse | null>(
    null,
  );
  const [availabilityNote, setAvailabilityNote] = useState<string | null>(null);
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'error'>(
    isReportBuilder ? 'loading' : 'ready',
  );
  const [loadError, setLoadError] = useState('Unable to load report builder.');
  const [savedLayouts, setSavedLayouts] = useState<SavedReportLayout[]>([]);
  const [savedNote, setSavedNote] = useState<string | null>(null);
  const [pendingLayoutAction, setPendingLayoutAction] = useState<
    'rename' | 'delete' | 'share' | null
  >(null);
  // The persisted row id (when the layout lives in the backend), so subsequent
  // saves PATCH the same record instead of creating duplicates.
  const remoteId = useRef<string | null>(null);

  useEffect(() => {
    if (isReportBuilder) return;
    void loadAll(tenantId);
  }, [isReportBuilder, loadAll, tenantId]);

  // Hydrate the legacy dashboard preview from the backend once on mount.
  // Best-effort: any failure leaves the localStorage/default layout in place.
  useEffect(() => {
    if (isReportBuilder) return;
    const controller = new AbortController();
    let active = true;
    listSavedLayouts({ signal: controller.signal })
      .then((rows) => {
        if (!active || rows.length === 0) return;
        const match = rows.find((row) => row.config?.id === liveDashboardLayout.id) ?? rows[0];
        if (match?.config) {
          remoteId.current = match.id;
          setLayout(match.config);
        }
      })
      .catch(() => {
        /* offline / unauthenticated - keep the local layout */
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [isReportBuilder]);

  useEffect(() => {
    if (!reportId) return;
    const controller = new AbortController();
    let active = true;

    async function loadReportBuilder() {
      setLoadState('loading');
      setSavedNote(null);
      setAvailabilityNote(null);
      setDataAvailability(null);
      try {
        const reportPayload = await getReport(reportId as string, controller.signal);
        const [previewPayload, catalogPayload, availabilityPayload] = await Promise.all([
          previewReport(reportId as string, {}, controller.signal),
          fetchReportingCatalog(controller.signal),
          fetchReportDataAvailability(
            reportAvailabilityQuery(reportPayload),
            controller.signal,
          ).catch(() => null),
        ]);
        const generatedLayout = annotateLayoutAvailability(
          reportPreviewToLayout(previewPayload),
          availabilityPayload,
        );
        const governedSourceLayout: DashboardLayoutConfig = {
          ...generatedLayout,
          widgets: mergeGovernedWidgets(
            generatedLayout.widgets,
            reportingCatalogToWidgets(catalogPayload, availabilityPayload),
          ),
        };
        const reportSavedRows = await listSavedLayouts({
          configId: generatedLayout.id,
          signal: controller.signal,
        })
          .then((rows) => rows.filter((row) => row.config?.id === generatedLayout.id))
          .catch(() => []);
        const remoteMatch = reportSavedRows[0];
        const localLayout = loadLayout(generatedLayout.id);
        const selectedLayout = annotateLayoutAvailability(
          remoteMatch?.config ?? localLayout ?? generatedLayout,
          availabilityPayload,
          governedSourceLayout,
        );

        if (!active) return;
        remoteId.current = remoteMatch?.id ?? null;
        setReport(reportPayload);
        setSourceLayout(governedSourceLayout);
        setCatalogSchemaVersion(catalogPayload.schema_version);
        setDataAvailability(availabilityPayload);
        setAvailabilityNote(
          availabilityPayload
            ? 'Runtime metric availability loaded from stored report data.'
            : 'Runtime metric availability unavailable; using governed preview only.',
        );
        setSavedLayouts(reportSavedRows);
        setLayout(selectedLayout);
        setLoadState('ready');
      } catch (err) {
        if (!active || controller.signal.aborted) return;
        setLoadError(err instanceof Error ? err.message : 'Unable to load report builder.');
        setLoadState('error');
      }
    }

    void loadReportBuilder();
    return () => {
      active = false;
      controller.abort();
    };
  }, [reportId]);

  const resolveData = useMemo(() => {
    if (isReportBuilder) {
      return undefined;
    }
    return createStoreResolver({
      summary: (summary as Record<string, unknown> | null) ?? undefined,
      parish: (parish as ReadonlyArray<Record<string, unknown>> | null) ?? undefined,
    });
  }, [isReportBuilder, summary, parish]);

  const handleSave = useCallback(
    (next: DashboardLayoutConfig) => {
      const currentSavedRow = savedLayouts.find((row) => row.id === remoteId.current);

      // Always keep a local copy so the layout survives an offline reload.
      saveLayout(next);
      setSavedNote('Saving...');
      saveLayoutToApi(next, {
        id: remoteId.current ?? undefined,
        name: currentSavedRow?.name || next.title || report?.name || 'Report layout',
        is_shared: currentSavedRow?.is_shared,
      })
        .then((row) => {
          remoteId.current = row.id;
          setSavedLayouts((current) => [row, ...current.filter((entry) => entry.id !== row.id)]);
          setSavedNote('Saved to your account');
        })
        .catch(() => {
          setSavedNote('Saved to this browser (offline)');
        });
    },
    [report?.name, savedLayouts],
  );

  const handleSelectSavedLayout = useCallback(
    (event: ChangeEvent<HTMLSelectElement>) => {
      const nextId = event.target.value;
      if (nextId === 'browser') {
        remoteId.current = null;
        setSavedNote('Using browser copy');
        return;
      }

      const selected = savedLayouts.find((row) => row.id === nextId);
      if (!selected) return;
      remoteId.current = selected.id;
      const selectedLayout = annotateLayoutAvailability(
        selected.config,
        dataAvailability,
        sourceLayout,
      );
      saveLayout(selectedLayout);
      setLayout(selectedLayout);
      setSavedNote(`Loaded ${selected.name}`);
    },
    [dataAvailability, savedLayouts, sourceLayout],
  );

  const handleRenameSavedLayout = useCallback(async () => {
    const currentId = remoteId.current;
    if (!currentId) {
      setSavedNote('Save before renaming');
      return;
    }
    const currentSavedRow = savedLayouts.find((row) => row.id === currentId);
    const currentName = currentSavedRow?.name || layout.title;
    const nextName = window.prompt('Rename saved layout', currentName);
    const trimmed = nextName?.trim();
    if (!trimmed || trimmed === currentName) return;

    setPendingLayoutAction('rename');
    setSavedNote(null);
    try {
      const row = await updateSavedLayout(currentId, { name: trimmed });
      setSavedLayouts((current) => current.map((entry) => (entry.id === row.id ? row : entry)));
      setSavedNote('Layout renamed');
    } catch (error) {
      setSavedNote(error instanceof Error ? error.message : 'Unable to rename saved layout.');
    } finally {
      setPendingLayoutAction(null);
    }
  }, [layout.title, savedLayouts]);

  const handleDeleteSavedLayout = useCallback(async () => {
    const currentId = remoteId.current;
    if (!currentId) {
      setSavedNote('No saved layout selected');
      return;
    }
    const currentSavedRow = savedLayouts.find((row) => row.id === currentId);
    const currentName = currentSavedRow?.name || layout.title;
    if (!window.confirm(`Delete "${currentName}" permanently?`)) return;

    setPendingLayoutAction('delete');
    setSavedNote(null);
    try {
      await deleteSavedLayout(currentId);
      remoteId.current = null;
      setSavedLayouts((current) => current.filter((entry) => entry.id !== currentId));
      saveLayout(layout);
      setSavedNote('Saved layout deleted');
    } catch (error) {
      setSavedNote(error instanceof Error ? error.message : 'Unable to delete saved layout.');
    } finally {
      setPendingLayoutAction(null);
    }
  }, [layout, savedLayouts]);

  const activeSavedLayoutId = remoteId.current ?? 'browser';
  const activeSavedLayout = savedLayouts.find((row) => row.id === remoteId.current) ?? null;

  const handleToggleSharedLayout = useCallback(async (event: ChangeEvent<HTMLInputElement>) => {
    const currentId = remoteId.current;
    if (!currentId) {
      setSavedNote('Save before sharing');
      return;
    }
    const nextShared = event.target.checked;

    setPendingLayoutAction('share');
    setSavedNote(null);
    try {
      const row = await updateSavedLayout(currentId, { is_shared: nextShared });
      setSavedLayouts((current) => current.map((entry) => (entry.id === row.id ? row : entry)));
      setSavedNote(nextShared ? 'Shared with tenant' : 'Private to you');
    } catch (error) {
      setSavedNote(error instanceof Error ? error.message : 'Unable to update sharing.');
    } finally {
      setPendingLayoutAction(null);
    }
  }, []);

  const handleSaveLegacy = (next: DashboardLayoutConfig) => {
    // Always keep a local copy so the layout survives an offline reload.
    saveLayout(next);
    setSavedNote('Saving...');
    saveLayoutToApi(next, {
      id: remoteId.current ?? undefined,
      name: next.title || report?.name || 'Report layout',
    })
      .then((row) => {
        remoteId.current = row.id;
        setSavedNote('Saved to your account');
      })
      .catch(() => {
        setSavedNote('Saved to this browser (offline)');
      });
  };

  if (isReportBuilder && loadState === 'loading') {
    return (
      <section className="dashboardPage" aria-label="Report layout builder loading">
        <header className="dashboardPageHeader">
          <p className="dashboardEyebrow">Report builder</p>
          <h1 className="dashboardHeading">Loading layout builder</h1>
        </header>
        <SkeletonLoader variant="card" count={2} />
      </section>
    );
  }

  if (isReportBuilder && loadState === 'error') {
    return (
      <DashboardState
        variant="error"
        layout="page"
        title="Report builder unavailable"
        message={loadError}
      />
    );
  }

  return (
    <section className="dashboardPage" aria-label="Report layout preview">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Report builder · {editing ? 'edit' : 'preview'}</p>
        <h1 className="dashboardHeading">
          {isReportBuilder ? `${report?.name ?? 'Report'} layout` : 'Config-driven layout'}
        </h1>
        <p className="muted">
          {isReportBuilder
            ? `This canvas starts from the governed report preview and backend reporting catalog${
                catalogSchemaVersion ? ` (${catalogSchemaVersion})` : ''
              }. Edits are saved as tenant-scoped report layout configs.`
            : 'This entire report is rendered from a saved layout config and bound to live dashboard data. Switch to edit mode to drag, resize, add, and remove charts.'}
        </p>
        <div className="report-builder-actions">
          {isReportBuilder && reportId ? (
            <Link to={`/reports/${reportId}`} className="button tertiary">
              Back to rendered report
            </Link>
          ) : null}
          <button type="button" className="button" onClick={() => setEditing((v) => !v)}>
            {editing ? 'Done editing' : 'Edit layout'}
          </button>
          {savedNote ? <span className="muted">{savedNote}</span> : null}
        </div>
        {isReportBuilder && availabilityNote ? <p className="muted">{availabilityNote}</p> : null}
        {isReportBuilder ? (
          <div className="report-layout-manager" aria-label="Saved report layouts">
            <label className="report-layout-manager__field">
              <span>Saved layout</span>
              <select value={activeSavedLayoutId} onChange={handleSelectSavedLayout}>
                <option value="browser">Browser copy</option>
                {savedLayouts.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.name}
                    {row.is_shared ? ' (shared)' : ''}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="button tertiary"
              onClick={() => void handleRenameSavedLayout()}
              disabled={activeSavedLayoutId === 'browser' || pendingLayoutAction !== null}
            >
              {pendingLayoutAction === 'rename' ? 'Renaming...' : 'Rename'}
            </button>
            <button
              type="button"
              className="button tertiary"
              onClick={() => void handleDeleteSavedLayout()}
              disabled={activeSavedLayoutId === 'browser' || pendingLayoutAction !== null}
            >
              {pendingLayoutAction === 'delete' ? 'Deleting...' : 'Delete'}
            </button>
            <label className="report-layout-manager__toggle">
              <input
                type="checkbox"
                checked={Boolean(activeSavedLayout?.is_shared)}
                onChange={(event) => void handleToggleSharedLayout(event)}
                disabled={activeSavedLayoutId === 'browser' || pendingLayoutAction !== null}
              />
              <span>Share with tenant</span>
            </label>
          </div>
        ) : null}
      </header>

      {editing ? (
        <LayoutEditor
          layout={layout}
          onChange={setLayout}
          onSave={isReportBuilder ? handleSave : handleSaveLegacy}
          resolveData={resolveData as ((widget: DashboardWidget) => unknown) | undefined}
          availableWidgets={isReportBuilder ? sourceLayout?.widgets : undefined}
          placeholderWidgetTypes={isReportBuilder ? ['note'] : undefined}
        />
      ) : (
        <GridCanvas
          layout={layout}
          resolveData={resolveData as ((widget: DashboardWidget) => unknown) | undefined}
        />
      )}
    </section>
  );
};

export default ReportLayoutPreview;
