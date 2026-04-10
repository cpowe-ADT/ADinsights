import { useCallback, useEffect, useState } from 'react';
import { Link, useParams, useLocation } from 'react-router-dom';

import DashboardState from '../components/DashboardState';
import { fetchUploadStatus, type UploadMetricsStatus } from '../lib/dataService';
import { formatAbsoluteTime, formatRelativeTime } from '../lib/format';
import type { UploadedDataset } from '../lib/uploadedMetrics';
import '../styles/phase2.css';
import '../styles/dashboard.css';

/**
 * Upload detail page at /dashboards/uploads/:uploadId
 *
 * Approach: The backend exposes a single upload status endpoint (/uploads/metrics/)
 * rather than individual upload records by ID. This page supports two data sources:
 *
 * 1. Route state — the upload list page can pass { dataset, status } when linking here,
 *    providing immediate data without an extra fetch.
 * 2. Fetch fallback — if no route state is available (e.g. direct navigation),
 *    the page fetches the current upload status from the backend.
 *
 * The uploadId param can be "current" for the active upload or any future ID
 * if the backend adds per-upload tracking.
 */

interface LocationState {
  dataset?: UploadedDataset;
  status?: UploadMetricsStatus;
}

type PageState = 'loading' | 'ready' | 'empty' | 'error';

interface UploadDetail {
  snapshotGeneratedAt?: string;
  campaignRowCount: number;
  parishRowCount: number;
  budgetRowCount: number;
  dataset?: UploadedDataset;
}

const StatusPill = ({ hasData }: { hasData: boolean }) => (
  <span className={`phase2-pill phase2-pill--${hasData ? 'success' : 'muted'}`}>
    {hasData ? 'Success' : 'No data'}
  </span>
);

const renderPreviewTable = (rows: Record<string, unknown>[], label: string) => {
  if (rows.length === 0) {
    return null;
  }

  const preview = rows.slice(0, 10);
  const columns = Object.keys(preview[0] ?? {});

  return (
    <article className="phase2-card">
      <h3>{label} preview ({rows.length} total rows, showing first {preview.length})</h3>
      <div className="table-responsive">
        <table>
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col} scope="col">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {preview.map((row, idx) => (
              <tr key={`preview-${idx}`}>
                {columns.map((col) => (
                  <td key={`${idx}-${col}`}>
                    {typeof row[col] === 'undefined' || row[col] === null
                      ? '\u2014'
                      : String(row[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </article>
  );
};

const CsvUploadDetail = () => {
  const { uploadId } = useParams<{ uploadId: string }>();
  const location = useLocation();
  const locationState = (location.state ?? {}) as LocationState;

  const [pageState, setPageState] = useState<PageState>('loading');
  const [detail, setDetail] = useState<UploadDetail | null>(null);
  const [errorMessage, setErrorMessage] = useState('Unable to load upload details.');

  const load = useCallback(async () => {
    // If route state was provided, use it directly
    if (locationState.status?.has_upload || locationState.dataset) {
      const status = locationState.status;
      const dataset = locationState.dataset;
      setDetail({
        snapshotGeneratedAt: status?.snapshot_generated_at ?? dataset?.uploadedAt,
        campaignRowCount:
          status?.counts?.campaign_rows ?? dataset?.campaignMetrics?.length ?? 0,
        parishRowCount:
          status?.counts?.parish_rows ?? dataset?.parishMetrics?.length ?? 0,
        budgetRowCount:
          status?.counts?.budget_rows ?? dataset?.budgets?.length ?? 0,
        dataset,
      });
      setPageState('ready');
      return;
    }

    // Fallback: fetch from backend
    setPageState('loading');
    try {
      const status = await fetchUploadStatus();
      if (!status.has_upload) {
        setPageState('empty');
        return;
      }
      setDetail({
        snapshotGeneratedAt: status.snapshot_generated_at,
        campaignRowCount: status.counts?.campaign_rows ?? 0,
        parishRowCount: status.counts?.parish_rows ?? 0,
        budgetRowCount: status.counts?.budget_rows ?? 0,
      });
      setPageState('ready');
    } catch (err) {
      setPageState('error');
      setErrorMessage(err instanceof Error ? err.message : 'Unable to load upload details.');
    }
  }, [locationState.status, locationState.dataset]);

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (pageState === 'loading') {
    return (
      <DashboardState variant="loading" layout="page" message="Loading upload detail\u2026" />
    );
  }

  if (pageState === 'error') {
    return (
      <DashboardState
        variant="error"
        layout="page"
        title="Upload unavailable"
        message={errorMessage}
        actionLabel="Retry"
        onAction={() => void load()}
      />
    );
  }

  if (pageState === 'empty' || !detail) {
    return (
      <section className="phase2-page">
        <header className="phase2-page__header">
          <div>
            <p className="dashboardEyebrow">CSV Uploads</p>
            <h1 className="dashboardHeading">Upload not found</h1>
          </div>
          <div className="phase2-row-actions">
            <Link to="/dashboards/uploads" className="button tertiary">
              Back to uploads
            </Link>
          </div>
        </header>
        <DashboardState
          variant="empty"
          layout="panel"
          title="No upload data"
          message="This upload does not exist or has been cleared."
        />
      </section>
    );
  }

  const totalRows = detail.campaignRowCount + detail.parishRowCount + detail.budgetRowCount;
  const datasetTypes: string[] = [];
  if (detail.campaignRowCount > 0) datasetTypes.push('campaign');
  if (detail.parishRowCount > 0) datasetTypes.push('parish');
  if (detail.budgetRowCount > 0) datasetTypes.push('budget');

  const campaignColumns = detail.dataset?.campaignMetrics?.[0]
    ? Object.keys(detail.dataset.campaignMetrics[0])
    : [];
  const parishColumns = detail.dataset?.parishMetrics?.[0]
    ? Object.keys(detail.dataset.parishMetrics[0])
    : [];
  const budgetColumns = detail.dataset?.budgets?.[0]
    ? Object.keys(detail.dataset.budgets[0])
    : [];

  return (
    <section className="phase2-page">
      <header className="phase2-page__header">
        <div>
          <p className="dashboardEyebrow">CSV Uploads</p>
          <h1 className="dashboardHeading">
            Upload {uploadId === 'current' ? '(current)' : uploadId}
          </h1>
          <p className="phase2-page__subhead">
            Uploaded dataset details and data preview.
          </p>
        </div>
        <div className="phase2-row-actions">
          <Link to="/dashboards/uploads" className="button tertiary">
            Back to uploads
          </Link>
        </div>
      </header>

      <article className="phase2-card">
        <h3>Upload summary</h3>
        <p>
          Status: <StatusPill hasData={totalRows > 0} />
        </p>
        <p>
          Dataset types: <strong>{datasetTypes.length > 0 ? datasetTypes.join(', ') : 'none'}</strong>
        </p>
        <p>
          Upload date:{' '}
          <strong>
            {formatRelativeTime(detail.snapshotGeneratedAt) ?? 'Unknown'}
          </strong>
          {detail.snapshotGeneratedAt ? (
            <span className="status-message muted">
              {' '}({formatAbsoluteTime(detail.snapshotGeneratedAt)})
            </span>
          ) : null}
        </p>
        <p>
          Total rows: <strong>{totalRows}</strong>
        </p>
        <p>
          Campaign rows: <strong>{detail.campaignRowCount}</strong>
          {campaignColumns.length > 0 ? (
            <span className="status-message muted"> — columns: {campaignColumns.join(', ')}</span>
          ) : null}
        </p>
        <p>
          Parish rows: <strong>{detail.parishRowCount}</strong>
          {parishColumns.length > 0 ? (
            <span className="status-message muted"> — columns: {parishColumns.join(', ')}</span>
          ) : null}
        </p>
        <p>
          Budget rows: <strong>{detail.budgetRowCount}</strong>
          {budgetColumns.length > 0 ? (
            <span className="status-message muted"> — columns: {budgetColumns.join(', ')}</span>
          ) : null}
        </p>
      </article>

      {detail.dataset?.campaignMetrics
        ? renderPreviewTable(
            detail.dataset.campaignMetrics as unknown as Record<string, unknown>[],
            'Campaign metrics',
          )
        : null}

      {detail.dataset?.parishMetrics
        ? renderPreviewTable(
            detail.dataset.parishMetrics as unknown as Record<string, unknown>[],
            'Parish metrics',
          )
        : null}

      {detail.dataset?.budgets
        ? renderPreviewTable(
            detail.dataset.budgets as unknown as Record<string, unknown>[],
            'Budget data',
          )
        : null}

      {!detail.dataset ? (
        <article className="phase2-card">
          <h3>Data preview</h3>
          <p className="status-message muted">
            Data preview is only available when navigating from the upload page. Visit the
            upload page to view row-level data.
          </p>
        </article>
      ) : null}
    </section>
  );
};

export default CsvUploadDetail;
