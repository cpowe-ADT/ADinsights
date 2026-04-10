import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import DashboardState from '../components/DashboardState';
import {
  createReportExport,
  getReport,
  listReportExports,
  updateReport,
  type ReportDefinition,
  type ReportExportJob,
} from '../lib/phase2Api';
import { API_BASE_URL } from '../lib/apiClient';
import { formatAbsoluteTime, formatRelativeTime } from '../lib/format';
import '../styles/phase2.css';
import '../styles/dashboard.css';

const exportFormats: Array<'csv' | 'pdf' | 'png'> = ['csv', 'pdf', 'png'];
const POLL_INTERVAL_MS = 5_000;
const MAX_POLLS = 12;

function buildDownloadUrl(jobId: string): string {
  const base = API_BASE_URL.replace(/\/$/, '');
  return `${base}/exports/${jobId}/download/`;
}

const ReportDetailPage = () => {
  const { reportId } = useParams<{ reportId: string }>();
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [report, setReport] = useState<ReportDefinition | null>(null);
  const [exports, setExports] = useState<ReportExportJob[]>([]);
  const [error, setError] = useState<string>('Unable to load report.');
  const [creatingFormat, setCreatingFormat] = useState<string | null>(null);

  // Inline editing state
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editActive, setEditActive] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Polling state
  const [polling, setPolling] = useState(false);
  const pollCountRef = useRef(0);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    if (!reportId) {
      setState('error');
      setError('Report ID is missing.');
      return;
    }

    setState('loading');
    try {
      const [reportPayload, exportsPayload] = await Promise.all([
        getReport(reportId),
        listReportExports(reportId),
      ]);
      setReport(reportPayload);
      setExports(exportsPayload);
      setState('ready');
    } catch (err) {
      setState('error');
      setError(err instanceof Error ? err.message : 'Unable to load report.');
    }
  }, [reportId]);

  useEffect(() => {
    void load();
  }, [load]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  const stopPolling = useCallback(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    pollCountRef.current = 0;
    setPolling(false);
  }, []);

  const startPolling = useCallback(() => {
    if (!reportId) return;

    stopPolling();
    pollCountRef.current = 0;
    setPolling(true);

    pollIntervalRef.current = setInterval(async () => {
      pollCountRef.current += 1;

      try {
        const freshExports = await listReportExports(reportId);
        setExports(freshExports);

        const hasPending = freshExports.some(
          (job) => job.status === 'queued' || job.status === 'running',
        );

        if (!hasPending || pollCountRef.current >= MAX_POLLS) {
          stopPolling();
        }
      } catch {
        stopPolling();
      }
    }, POLL_INTERVAL_MS);
  }, [reportId, stopPolling]);

  const requestExport = useCallback(
    async (format: 'csv' | 'pdf' | 'png') => {
      if (!reportId) {
        return;
      }
      setCreatingFormat(format);
      try {
        await createReportExport(reportId, format);
        await load();
        startPolling();
      } finally {
        setCreatingFormat(null);
      }
    },
    [load, reportId, startPolling],
  );

  const enterEditMode = useCallback(() => {
    if (!report) return;
    setEditName(report.name);
    setEditDescription(report.description);
    setEditActive(report.is_active);
    setSaveError(null);
    setEditing(true);
  }, [report]);

  const cancelEdit = useCallback(() => {
    setEditing(false);
    setSaveError(null);
  }, []);

  const saveEdit = useCallback(async () => {
    if (!reportId) return;
    setSaving(true);
    setSaveError(null);
    try {
      await updateReport(reportId, {
        name: editName,
        description: editDescription,
        is_active: editActive,
      });
      await load();
      setEditing(false);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save changes.');
    } finally {
      setSaving(false);
    }
  }, [reportId, editName, editDescription, editActive, load]);

  if (state === 'loading') {
    return <DashboardState variant="loading" layout="page" message="Loading report…" />;
  }

  if (state === 'error' || !report) {
    return (
      <DashboardState
        variant="error"
        layout="page"
        title="Report unavailable"
        message={error}
        actionLabel="Retry"
        onAction={() => void load()}
      />
    );
  }

  return (
    <section className="phase2-page">
      <header className="phase2-page__header">
        <div>
          <p className="dashboardEyebrow">Reporting</p>
          {editing ? (
            <>
              <input
                type="text"
                className="phase2-input"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                aria-label="Report name"
              />
              <textarea
                className="phase2-input"
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
                aria-label="Report description"
                rows={2}
              />
              <label>
                <input
                  type="checkbox"
                  checked={editActive}
                  onChange={(e) => setEditActive(e.target.checked)}
                />{' '}
                Active
              </label>
              {saveError && <p className="phase2-error">{saveError}</p>}
            </>
          ) : (
            <>
              <h1 className="dashboardHeading">{report.name}</h1>
              <p className="phase2-page__subhead">{report.description || 'No description provided.'}</p>
            </>
          )}
        </div>
        <div className="phase2-row-actions">
          <Link to="/reports" className="button tertiary">
            Back to reports
          </Link>
          {editing ? (
            <>
              <button type="button" className="button primary" onClick={() => void saveEdit()} disabled={saving}>
                {saving ? 'Saving…' : 'Save'}
              </button>
              <button type="button" className="button secondary" onClick={cancelEdit} disabled={saving}>
                Cancel
              </button>
            </>
          ) : (
            <>
              <button type="button" className="button secondary" onClick={enterEditMode}>
                Edit
              </button>
              <button type="button" className="button secondary" onClick={() => void load()}>
                Refresh
              </button>
            </>
          )}
        </div>
      </header>

      <article className="phase2-card">
        <h3>Export actions</h3>
        <p className="phase2-note">Request CSV, PDF, or PNG exports for this report.</p>
        <div className="phase2-row-actions">
          {exportFormats.map((format) => (
            <button
              key={format}
              type="button"
              className="button secondary"
              onClick={() => void requestExport(format)}
              disabled={creatingFormat !== null}
            >
              {creatingFormat === format
                ? `Requesting ${format.toUpperCase()}…`
                : `Request ${format.toUpperCase()}`}
            </button>
          ))}
        </div>
        {polling && <p className="phase2-note">Checking export status...</p>}
      </article>

      {exports.length === 0 ? (
        <DashboardState
          variant="empty"
          layout="page"
          title="No export jobs yet"
          message="Request an export to begin tracking job progress."
        />
      ) : (
        <table className="phase2-table">
          <thead>
            <tr>
              <th>Format</th>
              <th>Status</th>
              <th>Created</th>
              <th>Completed</th>
              <th>Artifact</th>
            </tr>
          </thead>
          <tbody>
            {exports.map((job) => (
              <tr key={job.id}>
                <td>{job.export_format.toUpperCase()}</td>
                <td>
                  <span className={`phase2-pill phase2-pill--${job.status}`}>{job.status}</span>
                </td>
                <td>
                  {formatRelativeTime(job.created_at)} ({formatAbsoluteTime(job.created_at)})
                </td>
                <td>
                  {job.completed_at
                    ? `${formatRelativeTime(job.completed_at)} (${formatAbsoluteTime(job.completed_at)})`
                    : 'In progress'}
                </td>
                <td>
                  {job.status === 'completed' && job.artifact_path ? (
                    <a href={buildDownloadUrl(job.id)} download>
                      Download
                    </a>
                  ) : job.artifact_path ? (
                    <code>{job.artifact_path}</code>
                  ) : (
                    'Pending'
                  )}
                  {job.error_message ? <div>{job.error_message}</div> : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
};

export default ReportDetailPage;
