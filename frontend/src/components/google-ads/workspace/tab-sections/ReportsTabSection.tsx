import { useCallback, useEffect, useMemo, useState } from 'react';

import { EmptyState, KpiTile } from '../../../viz';
import {
  createGoogleAdsExport,
  createGoogleAdsSavedView,
  fetchGoogleAdsExportStatus,
  fetchGoogleAdsSavedViews,
  type GoogleAdsExportJob,
  type GoogleAdsSavedView,
} from '../../../../lib/googleAdsDashboard';
import { deriveExportJobStatusTone } from '../../../../lib/googleAdsAggregates';

type Props = {
  /**
   * Optional pre-loaded saved views (e.g. from the workspace hook). When
   * omitted the tab loads them itself.
   */
  initialSavedViews?: GoogleAdsSavedView[];
};

const EmptyIcon = () => (
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
    <rect x="4" y="3" width="16" height="18" rx="2" />
    <path d="M8 8h8M8 12h8M8 16h5" />
  </svg>
);

const STATUS_CHIP_CLASS: Record<string, string> = {
  success: 'badge badge--success',
  warning: 'badge badge--warning',
  danger: 'badge badge--danger',
  neutral: 'badge',
};

/**
 * Sprint 3 — Reports tab. Architect §6.10.
 *
 * Workflow tab: keep the form controls (saved-view create, CSV export) and
 * swap the two tables to viz-kit-styled rendering with status chips.
 *
 * Charts are intentionally absent (§6.10 — tables are already semantic).
 */
const ReportsTabSection = ({ initialSavedViews }: Props) => {
  const [savedViews, setSavedViews] = useState<GoogleAdsSavedView[]>(initialSavedViews ?? []);
  const [status, setStatus] = useState<'idle' | 'loading' | 'error'>(
    initialSavedViews ? 'idle' : 'loading',
  );
  const [error, setError] = useState('');
  const [viewName, setViewName] = useState('');
  const [job, setJob] = useState<GoogleAdsExportJob | null>(null);

  const loadSavedViews = useCallback(async () => {
    setStatus('loading');
    setError('');
    try {
      const rows = await fetchGoogleAdsSavedViews();
      setSavedViews(rows);
      setStatus('idle');
    } catch (err) {
      setStatus('error');
      setError(err instanceof Error ? err.message : 'Failed to load saved views.');
    }
  }, []);

  useEffect(() => {
    if (!initialSavedViews) {
      void loadSavedViews();
    }
  }, [initialSavedViews, loadSavedViews]);

  const handleCreateExport = useCallback(async () => {
    setError('');
    try {
      const created = await createGoogleAdsExport({
        export_format: 'csv',
        name: 'Google Ads Campaign Export',
      });
      setJob(created);
      if (created.id) {
        const refreshed = await fetchGoogleAdsExportStatus(created.id);
        setJob(refreshed);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create export.');
    }
  }, []);

  const handleCreateSavedView = useCallback(async () => {
    if (!viewName.trim()) return;
    setError('');
    try {
      await createGoogleAdsSavedView({
        name: viewName.trim(),
        description: 'Saved from Reports & Exports',
        filters: {},
        columns: [],
        is_shared: true,
      });
      setViewName('');
      await loadSavedViews();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create saved view.');
    }
  }, [loadSavedViews, viewName]);

  const sharedCount = useMemo(
    () => savedViews.filter((v) => v.is_shared).length,
    [savedViews],
  );

  const jobTone = job ? deriveExportJobStatusTone(job.status) : 'neutral';
  const jobChipClass = STATUS_CHIP_CLASS[jobTone] ?? STATUS_CHIP_CLASS.neutral;

  return (
    <div className="gads-workspace__tab-grid" data-testid="google-ads-reports-section">
      <section className="panel">
        <h2>Reports KPIs</h2>
        <div
          className="gads-workspace__kpi-grid"
          role="list"
          aria-label="Google Ads reports KPIs"
        >
          <KpiTile label="Total saved views" value={savedViews.length} format="number" />
          <KpiTile label="Shared views" value={sharedCount} format="number" />
        </div>
      </section>

      {error ? (
        <div className="panel" role="alert">
          {error}
        </div>
      ) : null}

      <section className="panel">
        <h2>Export</h2>
        <div className="dashboard-header__actions-row">
          <button type="button" className="button secondary" onClick={handleCreateExport}>
            Create CSV Export
          </button>
          {job?.download_url ? (
            <a className="button tertiary" href={job.download_url}>
              Download latest export
            </a>
          ) : null}
        </div>
        {job ? (
          <p className="dashboard-field__label" style={{ marginTop: '0.75rem' }}>
            Job {job.id}: <span className={jobChipClass}>{job.status}</span>
          </p>
        ) : null}
      </section>

      <section className="panel">
        <h2>Saved views</h2>
        <div className="dashboard-header__controls" style={{ marginBottom: '0.75rem' }}>
          <label className="dashboard-field">
            <span className="dashboard-field__label">Name</span>
            <input
              value={viewName}
              onChange={(event) => setViewName(event.target.value)}
              placeholder="Weekly executive filter set"
            />
          </label>
          <button type="button" className="button secondary" onClick={handleCreateSavedView}>
            Save view
          </button>
        </div>

        {status === 'loading' && savedViews.length === 0 ? (
          <p>Loading saved views...</p>
        ) : null}

        {status !== 'loading' && savedViews.length === 0 ? (
          <EmptyState
            icon={<EmptyIcon />}
            title="No saved views yet"
            message="Create a saved view to reuse a filter combination across dashboards."
            reasonCode="no_saved_views"
          />
        ) : null}

        {savedViews.length > 0 ? (
          <div className="table-responsive">
            <table className="dashboard-table">
              <thead>
                <tr className="dashboard-table__header-row">
                  <th className="dashboard-table__header-cell">Name</th>
                  <th className="dashboard-table__header-cell">Description</th>
                  <th className="dashboard-table__header-cell">Shared</th>
                  <th className="dashboard-table__header-cell">Updated</th>
                </tr>
              </thead>
              <tbody>
                {savedViews.map((view) => (
                  <tr
                    key={view.id}
                    className="dashboard-table__row dashboard-table__row--zebra"
                  >
                    <td className="dashboard-table__cell">{view.name}</td>
                    <td className="dashboard-table__cell">{view.description || '—'}</td>
                    <td className="dashboard-table__cell">
                      <span
                        className={view.is_shared ? 'badge badge--success' : 'badge'}
                        data-status-tone={view.is_shared ? 'success' : 'neutral'}
                      >
                        {view.is_shared ? 'Shared' : 'Private'}
                      </span>
                    </td>
                    <td className="dashboard-table__cell">{view.updated_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </div>
  );
};

export default ReportsTabSection;
