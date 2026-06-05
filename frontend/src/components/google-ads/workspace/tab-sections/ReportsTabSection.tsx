import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { EmptyState, KpiTile } from '../../../viz';
import {
  createGoogleAdsExport,
  createGoogleAdsSavedView,
  fetchGoogleAdsExportStatus,
  fetchGoogleAdsSavedViews,
  verifyGoogleAdsSavedView,
  type GoogleAdsExportJob,
  type GoogleAdsSavedView,
} from '../../../../lib/googleAdsDashboard';
import {
  deriveExportJobStatusTone,
  isTerminalExportStatus,
} from '../../../../lib/googleAdsAggregates';
import { ApiError } from '../../../../lib/apiClient';

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

// GA-A3 polling constants. Kept module-scoped so tests can import if ever
// needed and so the numbers are visible in one place.
const POLL_BASE_INTERVAL_MS = 3000;
const POLL_CEILING_MS = 60000;
const MAX_CONSECUTIVE_5XX = 3;

/**
 * Sprint 3 — Reports tab. Architect §6.10.
 *
 * Workflow tab: keep the form controls (saved-view create, CSV export) and
 * swap the two tables to viz-kit-styled rendering with status chips.
 *
 * GA-A3: after creating a CSV export the component polls
 * `/exports/<id>/` every 3s (setTimeout chain, not setInterval) until the
 * status is terminal, a 60s ceiling is hit, 3 consecutive 5xx responses
 * trigger a hard stop, or the component unmounts. Exponential backoff
 * (3 → 6 → 12s) is applied on 5xx responses.
 */
const ReportsTabSection = ({ initialSavedViews }: Props) => {
  const [savedViews, setSavedViews] = useState<GoogleAdsSavedView[]>(initialSavedViews ?? []);
  const [status, setStatus] = useState<'idle' | 'loading' | 'error'>(
    initialSavedViews ? 'idle' : 'loading',
  );
  const [error, setError] = useState('');
  const [viewName, setViewName] = useState('');
  const [job, setJob] = useState<GoogleAdsExportJob | null>(null);

  // GA-B2: drift banner state. Verification runs after the initial saved
  // views are available; failed verify calls silently drop from the count
  // so partial outages don't create false alarms.
  const [driftedViews, setDriftedViews] = useState<Array<{ id: string; name: string }>>([]);
  const [showBanner, setShowBanner] = useState(true);

  // Polling refs — mutable without triggering re-render.
  const mountedRef = useRef(true);
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollStartRef = useRef<number>(0);
  const consecutive5xxRef = useRef<number>(0);
  const pollAbortRef = useRef<AbortController | null>(null);

  const clearPollTimer = useCallback(() => {
    if (pollTimeoutRef.current !== null) {
      clearTimeout(pollTimeoutRef.current);
      pollTimeoutRef.current = null;
    }
  }, []);

  const cancelPolling = useCallback(() => {
    clearPollTimer();
    if (pollAbortRef.current) {
      pollAbortRef.current.abort();
      pollAbortRef.current = null;
    }
    consecutive5xxRef.current = 0;
    pollStartRef.current = 0;
  }, [clearPollTimer]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      cancelPolling();
    };
  }, [cancelPolling]);

  const loadSavedViews = useCallback(async () => {
    setStatus('loading');
    setError('');
    try {
      const rows = await fetchGoogleAdsSavedViews();
      if (!mountedRef.current) return;
      setSavedViews(rows);
      setStatus('idle');
    } catch (err) {
      if (!mountedRef.current) return;
      setStatus('error');
      setError(err instanceof Error ? err.message : 'Failed to load saved views.');
    }
  }, []);

  useEffect(() => {
    if (!initialSavedViews) {
      void loadSavedViews();
    }
  }, [initialSavedViews, loadSavedViews]);

  // GA-B2: verify each saved view against the backend vocabulary and
  // collect the ids/names that are drifted. `Promise.allSettled` so a
  // single failed verify doesn't break the banner; rejected entries drop
  // out of the count silently.
  useEffect(() => {
    if (!savedViews || savedViews.length === 0) {
      setDriftedViews([]);
      return;
    }
    let cancelled = false;
    void Promise.allSettled(savedViews.map((view) => verifyGoogleAdsSavedView(view.id))).then(
      (results) => {
        if (cancelled || !mountedRef.current) return;
        const drift: Array<{ id: string; name: string }> = [];
        results.forEach((r) => {
          if (r.status === 'fulfilled' && r.value && r.value.drift === true) {
            drift.push({ id: r.value.id, name: r.value.name });
          }
        });
        setDriftedViews(drift);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [savedViews]);

  const scheduleNextPoll = useCallback(
    (jobId: string, delayMs: number) => {
      if (!mountedRef.current) return;
      // Respect the 60s ceiling measured from the first poll.
      const elapsed = Date.now() - pollStartRef.current;
      if (elapsed >= POLL_CEILING_MS) {
        clearPollTimer();
        return;
      }
      clearPollTimer();
      pollTimeoutRef.current = setTimeout(() => {
        void pollOnce(jobId);
      }, delayMs);
    },
    // pollOnce is declared below; we rely on the closure via the setTimeout.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [clearPollTimer],
  );

  const pollOnce = useCallback(
    async (jobId: string) => {
      if (!mountedRef.current) return;
      // Ceiling check up-front in case the timer fired right at the edge.
      if (Date.now() - pollStartRef.current >= POLL_CEILING_MS) {
        return;
      }
      const controller = new AbortController();
      pollAbortRef.current = controller;
      try {
        const refreshed = await fetchGoogleAdsExportStatus(jobId);
        if (!mountedRef.current) return;
        consecutive5xxRef.current = 0;
        setJob(refreshed);
        if (isTerminalExportStatus(refreshed.status)) {
          cancelPolling();
          return;
        }
        scheduleNextPoll(jobId, POLL_BASE_INTERVAL_MS);
      } catch (err) {
        if (!mountedRef.current) return;
        const isServerError =
          err instanceof ApiError ? err.status >= 500 && err.status < 600 : false;
        if (isServerError) {
          consecutive5xxRef.current += 1;
          if (consecutive5xxRef.current >= MAX_CONSECUTIVE_5XX) {
            setJob((prev) =>
              prev
                ? {
                    ...prev,
                    status: 'failed',
                    error_message: 'Polling aborted after 3 consecutive errors.',
                  }
                : prev,
            );
            cancelPolling();
            return;
          }
          // Exponential backoff: 3s, 6s, 12s — indexed by retry count so the
          // NEXT attempt respects the spec.
          const backoffMs = POLL_BASE_INTERVAL_MS * 2 ** consecutive5xxRef.current;
          scheduleNextPoll(jobId, backoffMs);
          return;
        }
        // Non-5xx error — surface and stop.
        setError(err instanceof Error ? err.message : 'Failed to fetch export status.');
        cancelPolling();
      } finally {
        // Release the abort controller reference after the request resolves
        // so cleanup on unmount doesn't abort a completed fetch.
        if (pollAbortRef.current === controller) {
          pollAbortRef.current = null;
        }
      }
    },
    [cancelPolling, scheduleNextPoll],
  );

  const handleCreateExport = useCallback(async () => {
    setError('');
    // Cancel any in-flight polling loop before starting a new export.
    cancelPolling();
    try {
      const created = await createGoogleAdsExport({
        export_format: 'csv',
        name: 'Google Ads Campaign Export',
      });
      if (!mountedRef.current) return;
      setJob(created);
      if (!created.id) return;
      if (isTerminalExportStatus(created.status)) {
        // Sync backend already returned terminal — no polling needed.
        return;
      }
      pollStartRef.current = Date.now();
      consecutive5xxRef.current = 0;
      scheduleNextPoll(created.id, POLL_BASE_INTERVAL_MS);
    } catch (err) {
      if (!mountedRef.current) return;
      setError(err instanceof Error ? err.message : 'Failed to create export.');
    }
  }, [cancelPolling, scheduleNextPoll]);

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
      if (!mountedRef.current) return;
      setViewName('');
      await loadSavedViews();
    } catch (err) {
      if (!mountedRef.current) return;
      setError(err instanceof Error ? err.message : 'Failed to create saved view.');
    }
  }, [loadSavedViews, viewName]);

  const sharedCount = useMemo(() => savedViews.filter((v) => v.is_shared).length, [savedViews]);

  const jobTone = job ? deriveExportJobStatusTone(job.status) : 'neutral';
  const jobChipClass = STATUS_CHIP_CLASS[jobTone] ?? STATUS_CHIP_CLASS.neutral;

  return (
    <div className="gads-workspace__tab-grid" data-testid="google-ads-reports-section">
      <section className="panel">
        <h2>Reports KPIs</h2>
        <div className="gads-workspace__kpi-grid" role="list" aria-label="Google Ads reports KPIs">
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
            Job {job.id}:{' '}
            <span className={jobChipClass} data-testid="google-ads-export-status">
              {job.status}
            </span>
          </p>
        ) : null}
      </section>

      {driftedViews.length > 0 && showBanner ? (
        <aside role="status" className="panel panel--warning" data-testid="drift-banner">
          <p>
            {driftedViews.length} saved view(s) may be out of date:{' '}
            {driftedViews.map((v) => v.name).join(', ')}.
          </p>
          <button type="button" className="button tertiary" onClick={() => setShowBanner(false)}>
            Dismiss
          </button>
        </aside>
      ) : null}

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

        {status === 'loading' && savedViews.length === 0 ? <p>Loading saved views...</p> : null}

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
                  <tr key={view.id} className="dashboard-table__row dashboard-table__row--zebra">
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
