import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import DashboardState from '../components/DashboardState';
import {
  createReportExport,
  getReport,
  listReportExports,
  type ReportDefinition,
  type ReportExportJob,
} from '../lib/phase2Api';
import apiClient from '../lib/apiClient';
import { formatAbsoluteTime, formatRelativeTime } from '../lib/format';
import { useToastStore } from '../stores/useToastStore';
import '../styles/phase2.css';
import '../styles/dashboard.css';

const exportFormats: Array<'csv' | 'pdf' | 'png'> = ['csv', 'pdf', 'png'];

async function updateReport(
  reportId: string,
  payload: { name?: string; description?: string },
): Promise<ReportDefinition> {
  return apiClient.patch<ReportDefinition>(`/reports/${reportId}/`, payload);
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
  const [saving, setSaving] = useState(false);

  const addToast = useToastStore((s) => s.addToast);

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

  const startEditing = useCallback(() => {
    if (!report) return;
    setEditName(report.name);
    setEditDescription(report.description);
    setEditing(true);
  }, [report]);

  const cancelEditing = useCallback(() => {
    if (!report) return;
    setEditName(report.name);
    setEditDescription(report.description);
    setEditing(false);
  }, [report]);

  const saveEditing = useCallback(async () => {
    if (!reportId || !report) return;
    setSaving(true);
    try {
      const updated = await updateReport(reportId, {
        name: editName,
        description: editDescription,
      });
      setReport(updated);
      setEditing(false);
      addToast('Report updated');
    } catch {
      addToast('Failed to update', 'error');
    } finally {
      setSaving(false);
    }
  }, [reportId, report, editName, editDescription, addToast]);

  const requestExport = useCallback(
    async (format: 'csv' | 'pdf' | 'png') => {
      if (!reportId) {
        return;
      }
      setCreatingFormat(format);
      try {
        await createReportExport(reportId, format);
        await load();
      } finally {
        setCreatingFormat(null);
      }
    },
    [load, reportId],
  );

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
              <label className="phase2-form__field" htmlFor="edit-report-name">
                <span>Name</span>
                <input
                  id="edit-report-name"
                  className="phase2-input"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                />
              </label>
              <label className="phase2-form__field" htmlFor="edit-report-description">
                <span>Description</span>
                <input
                  id="edit-report-description"
                  className="phase2-input"
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                />
              </label>
            </>
          ) : (
            <>
              <h1 className="dashboardHeading">{report.name}</h1>
              <p className="phase2-page__subhead">
                {report.description || 'No description provided.'}
              </p>
            </>
          )}
        </div>
        <div className="phase2-row-actions">
          <Link to="/reports" className="button tertiary">
            Back to reports
          </Link>
          {editing ? (
            <>
              <button
                type="button"
                className="button secondary"
                onClick={cancelEditing}
                disabled={saving}
              >
                Cancel
              </button>
              <button
                type="button"
                className="button primary"
                onClick={() => void saveEditing()}
                disabled={saving}
              >
                {saving ? 'Saving…' : 'Save'}
              </button>
            </>
          ) : (
            <>
              <button type="button" className="button secondary" onClick={startEditing}>
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
                  {job.artifact_path ? <code>{job.artifact_path}</code> : 'Pending'}
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
