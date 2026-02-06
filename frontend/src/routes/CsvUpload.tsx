import type { ChangeEvent } from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import EmptyState from '../components/EmptyState';
import useDashboardStore from '../state/useDashboardStore';
import { ApiError } from '../lib/apiClient';
import { clearUploadedMetrics, fetchUploadStatus, uploadMetrics } from '../lib/dataService';
import {
  parseBudgetCsv,
  parseCampaignCsv,
  parseParishCsv,
  type UploadParseResult,
  type UploadedBudgetRow,
  type UploadedCampaignMetricRow,
  type UploadedDataset,
  type UploadedParishMetricRow,
} from '../lib/uploadedMetrics';

const UploadIcon = () => (
  <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="2.2">
    <rect x="10" y="10" width="28" height="28" rx="4" />
    <path d="M24 30V18" strokeLinecap="round" />
    <path d="M19 22l5-5 5 5" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M16 34h16" strokeLinecap="round" />
  </svg>
);

type UploadCardState<T> = {
  fileName?: string;
  file?: File;
  parsed?: UploadParseResult<T>;
  isLoading: boolean;
};

const REQUIRED_CAMPAIGN_COLUMNS = [
  'date',
  'campaign_id',
  'campaign_name',
  'platform',
  'spend',
  'impressions',
  'clicks',
  'conversions',
];

const OPTIONAL_CAMPAIGN_COLUMNS = ['parish', 'revenue', 'roas', 'status', 'objective'];

const REQUIRED_PARISH_COLUMNS = ['parish', 'spend', 'impressions', 'clicks', 'conversions'];

const REQUIRED_BUDGET_COLUMNS = ['month', 'campaign_name', 'planned_budget'];

const renderColumnList = (columns: string[]) => columns.join(', ');

const renderPreviewTable = (rows: Record<string, unknown>[]) => {
  if (rows.length === 0) {
    return <p className="status-message muted">No rows parsed yet.</p>;
  }

  const preview = rows.slice(0, 5);
  const columns = Object.keys(preview[0] ?? {});

  return (
    <div className="table-responsive upload-preview">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column} scope="col">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {preview.map((row, index) => (
            <tr key={`preview-row-${index}`}>
              {columns.map((column) => (
                <td key={`${index}-${column}`}>
                  {typeof row[column] === 'undefined' ? '—' : String(row[column])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

const renderIssues = (issues: string[], tone: 'error' | 'warning') => {
  if (issues.length === 0) {
    return null;
  }
  return (
    <ul className={`upload-issues ${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      {issues.map((issue) => (
        <li key={issue}>{issue}</li>
      ))}
    </ul>
  );
};

const CsvUpload = () => {
  const navigate = useNavigate();
  const { uploadedDataset, uploadedActive, setUploadedDataset, setUploadedActive, clearUploadedDataset } =
    useDashboardStore((state) => ({
      uploadedDataset: state.uploadedDataset,
      uploadedActive: state.uploadedActive,
      setUploadedDataset: state.setUploadedDataset,
      clearUploadedDataset: state.clearUploadedDataset,
      setUploadedActive: state.setUploadedActive,
    }));

  const [campaignState, setCampaignState] = useState<UploadCardState<UploadedCampaignMetricRow>>({
    isLoading: false,
  });
  const [parishState, setParishState] = useState<UploadCardState<UploadedParishMetricRow>>({
    isLoading: false,
  });
  const [budgetState, setBudgetState] = useState<UploadCardState<UploadedBudgetRow>>({
    isLoading: false,
  });
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [statusTone, setStatusTone] = useState<'success' | 'error' | 'muted'>('muted');
  const [backendStatus, setBackendStatus] = useState<{
    hasUpload: boolean;
    snapshotGeneratedAt?: string;
    counts?: { campaign_rows: number; parish_rows: number; budget_rows: number };
  }>({ hasUpload: false });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [uploadErrors, setUploadErrors] = useState<string[]>([]);
  const docsUrl =
    import.meta.env.VITE_DOCS_URL?.trim() ||
    'https://github.com/cpowe-ADT/ADinsights/blob/main/docs/runbooks/csv-uploads.md';

  const handleBack = useCallback(() => {
    navigate('/dashboards/campaigns');
  }, [navigate]);

  const handleViewDocs = useCallback(() => {
    if (typeof window !== 'undefined') {
      window.open(docsUrl, '_blank', 'noopener,noreferrer');
    }
  }, [docsUrl]);

  useEffect(() => {
    let cancelled = false;
    const loadStatus = async () => {
      try {
        const status = await fetchUploadStatus();
        if (cancelled) {
          return;
        }
        if (status.has_upload) {
          setBackendStatus({
            hasUpload: true,
            snapshotGeneratedAt: status.snapshot_generated_at,
            counts: status.counts,
          });
        }
      } catch (error) {
        if (!cancelled) {
          setStatusTone('error');
          setStatusMessage(
            error instanceof Error ? error.message : 'Unable to load upload status.',
          );
        }
      }
    };
    void loadStatus();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleFile = useCallback(
    async <T,>(
      file: File,
      parser: (text: string) => UploadParseResult<T>,
      setter: (state: UploadCardState<T>) => void,
    ) => {
      setter({ isLoading: true, fileName: file.name, file });
      const text = await file.text();
      const parsed = parser(text);
      setter({ isLoading: false, fileName: file.name, file, parsed });
    },
    [],
  );

  const handleCampaignUpload = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) {
        return;
      }
      void handleFile(file, parseCampaignCsv, setCampaignState);
    },
    [handleFile],
  );

  const handleParishUpload = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) {
        return;
      }
      void handleFile(file, parseParishCsv, setParishState);
    },
    [handleFile],
  );

  const handleBudgetUpload = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) {
        return;
      }
      void handleFile(file, parseBudgetCsv, setBudgetState);
    },
    [handleFile],
  );

  const parsedErrors = useMemo(() => {
    return (
      (campaignState.parsed?.errors?.length ?? 0) +
      (parishState.parsed?.errors?.length ?? 0) +
      (budgetState.parsed?.errors?.length ?? 0)
    );
  }, [campaignState.parsed?.errors, parishState.parsed?.errors, budgetState.parsed?.errors]);

  const parsedRowsCount = useMemo(() => {
    return (
      (campaignState.parsed?.rows.length ?? 0) +
      (parishState.parsed?.rows.length ?? 0) +
      (budgetState.parsed?.rows.length ?? 0)
    );
  }, [campaignState.parsed?.rows, parishState.parsed?.rows, budgetState.parsed?.rows]);

  const handleApply = useCallback(() => {
    if (!campaignState.file) {
      setStatusTone('error');
      setStatusMessage('Campaign CSV is required.');
      return;
    }
    const dataset: UploadedDataset = {
      campaignMetrics: campaignState.parsed?.rows ?? [],
      parishMetrics: parishState.parsed?.rows ?? [],
      budgets: budgetState.parsed?.rows ?? [],
      uploadedAt: new Date().toISOString(),
    };
    const formData = new FormData();
    formData.append('campaign_csv', campaignState.file);
    if (parishState.file) {
      formData.append('parish_csv', parishState.file);
    }
    if (budgetState.file) {
      formData.append('budget_csv', budgetState.file);
    }

    setIsSubmitting(true);
    setStatusMessage(null);
    setStatusTone('muted');
    uploadMetrics(formData)
      .then((response) => {
        setUploadedDataset(dataset, true);
        setUploadedActive(true);
        setBackendStatus({
          hasUpload: true,
          snapshotGeneratedAt: response.snapshot_generated_at,
          counts: response.counts,
        });
        if (response.warnings && response.warnings.length > 0) {
          setStatusTone('muted');
          setStatusMessage(`Uploaded with ${response.warnings.length} warnings.`);
        } else {
          setStatusTone('success');
          setStatusMessage('Upload applied to dashboards.');
        }
        setUploadErrors([]);
      })
      .catch((error) => {
        setStatusTone('error');
        if (error instanceof ApiError && error.payload?.errors?.length) {
          setUploadErrors(error.payload.errors);
          setStatusMessage('CSV validation failed. Fix the issues below.');
        } else {
          setUploadErrors([]);
          setStatusMessage(error instanceof Error ? error.message : 'Upload failed.');
        }
      })
      .finally(() => {
        setIsSubmitting(false);
      });
  }, [
    budgetState.file,
    budgetState.parsed?.rows,
    campaignState.file,
    campaignState.parsed?.rows,
    parishState.file,
    parishState.parsed?.rows,
    setUploadedActive,
    setUploadedDataset,
  ]);

  const handleToggleActive = useCallback(() => {
    setUploadedActive(!uploadedActive);
  }, [setUploadedActive, uploadedActive]);

  const handleClearUploads = useCallback(() => {
    setIsSubmitting(true);
    setStatusMessage(null);
    clearUploadedMetrics()
      .then(() => {
        clearUploadedDataset();
        setUploadedActive(false);
        setBackendStatus({ hasUpload: false });
        setCampaignState({ isLoading: false });
        setParishState({ isLoading: false });
        setBudgetState({ isLoading: false });
        setStatusTone('muted');
        setStatusMessage('Uploads cleared.');
      })
      .catch((error) => {
        setStatusTone('error');
        setStatusMessage(error instanceof Error ? error.message : 'Unable to clear uploads.');
        setUploadErrors([]);
      })
      .finally(() => {
        setIsSubmitting(false);
      });
  }, [clearUploadedDataset, setUploadedActive]);

  const hasUploads =
    (campaignState.parsed?.rows.length ?? 0) > 0 ||
    (parishState.parsed?.rows.length ?? 0) > 0 ||
    (budgetState.parsed?.rows.length ?? 0) > 0;

  const hasStoredUploads = backendStatus.hasUpload || Boolean(uploadedDataset);

  return (
    <div className="dashboard-grid single-panel">
      <section className="panel full-width">
        <div className="panel-header">
          <div className="panel-header__title-row">
            <h2>Upload CSV data</h2>
            {hasStoredUploads ? (
              <span className={`status-pill ${uploadedActive ? 'success' : 'muted'}`}>
                {uploadedActive ? 'Uploaded data active' : 'Uploaded data paused'}
              </span>
            ) : null}
          </div>
          <p className="status-message muted">
            Upload campaign, parish, and budget CSVs to power the dashboards without a live data
            source.
          </p>
          <button type="button" className="button tertiary" onClick={handleViewDocs}>
            View CSV format guide
          </button>
          {backendStatus.hasUpload ? (
            <p className="status-message muted">
                Last upload{' '}
                {backendStatus.snapshotGeneratedAt
                  ? new Date(backendStatus.snapshotGeneratedAt).toLocaleString()
                  : 'available'}
                {backendStatus.counts
                  ? ` · ${backendStatus.counts.campaign_rows} campaign rows, ${backendStatus.counts.parish_rows} parish rows, ${backendStatus.counts.budget_rows} budget rows`
                  : ''}
              </p>
            ) : null}
          </div>

        <div className="upload-grid">
          <section className="upload-panel">
            <div className="upload-panel__header">
              <div>
                <h3>Daily campaign metrics</h3>
                <p className="status-message muted">
                  Required columns: {renderColumnList(REQUIRED_CAMPAIGN_COLUMNS)}.
                </p>
                <p className="status-message muted">
                  Optional columns: {renderColumnList(OPTIONAL_CAMPAIGN_COLUMNS)}.
                </p>
              </div>
              <div className="upload-panel__actions">
                <a
                  className="button tertiary"
                  href="/templates/campaign_metrics.csv"
                  download
                >
                  Download template
                </a>
                <label className="button secondary upload-button">
                  Select CSV
                  <input type="file" accept=".csv,text/csv" onChange={handleCampaignUpload} />
                </label>
              </div>
            </div>
            {campaignState.isLoading ? <p className="status-message muted">Reading CSV…</p> : null}
            {campaignState.parsed ? (
              <p className="status-message">
                {campaignState.fileName ?? 'Campaign CSV'} · {campaignState.parsed.rows.length} rows
              </p>
            ) : null}
            {renderIssues(campaignState.parsed?.errors ?? [], 'error')}
            {renderIssues(campaignState.parsed?.warnings ?? [], 'warning')}
            {campaignState.parsed
              ? renderPreviewTable(campaignState.parsed.rows as Record<string, unknown>[])
              : null}
          </section>

          <section className="upload-panel">
            <div className="upload-panel__header">
              <div>
                <h3>Parish metrics</h3>
                <p className="status-message muted">
                  Required columns: {renderColumnList(REQUIRED_PARISH_COLUMNS)}.
                </p>
              </div>
              <div className="upload-panel__actions">
                <a
                  className="button tertiary"
                  href="/templates/parish_metrics.csv"
                  download
                >
                  Download template
                </a>
                <label className="button secondary upload-button">
                  Select CSV
                  <input type="file" accept=".csv,text/csv" onChange={handleParishUpload} />
                </label>
              </div>
            </div>
            {parishState.isLoading ? <p className="status-message muted">Reading CSV…</p> : null}
            {parishState.parsed ? (
              <p className="status-message">
                {parishState.fileName ?? 'Parish CSV'} · {parishState.parsed.rows.length} rows
              </p>
            ) : null}
            {renderIssues(parishState.parsed?.errors ?? [], 'error')}
            {renderIssues(parishState.parsed?.warnings ?? [], 'warning')}
            {parishState.parsed
              ? renderPreviewTable(parishState.parsed.rows as Record<string, unknown>[])
              : null}
          </section>

          <section className="upload-panel">
            <div className="upload-panel__header">
              <div>
                <h3>Monthly budgets</h3>
                <p className="status-message muted">
                  Required columns: {renderColumnList(REQUIRED_BUDGET_COLUMNS)}.
                </p>
              </div>
              <div className="upload-panel__actions">
                <a
                  className="button tertiary"
                  href="/templates/budget_metrics.csv"
                  download
                >
                  Download template
                </a>
                <label className="button secondary upload-button">
                  Select CSV
                  <input type="file" accept=".csv,text/csv" onChange={handleBudgetUpload} />
                </label>
              </div>
            </div>
            {budgetState.isLoading ? <p className="status-message muted">Reading CSV…</p> : null}
            {budgetState.parsed ? (
              <p className="status-message">
                {budgetState.fileName ?? 'Budget CSV'} · {budgetState.parsed.rows.length} rows
              </p>
            ) : null}
            {renderIssues(budgetState.parsed?.errors ?? [], 'error')}
            {renderIssues(budgetState.parsed?.warnings ?? [], 'warning')}
            {budgetState.parsed
              ? renderPreviewTable(budgetState.parsed.rows as Record<string, unknown>[])
              : null}
          </section>
        </div>

        {parsedErrors > 0 ? (
          <div className="status-message error" role="alert">
            Fix {parsedErrors} issues before applying the uploads.
          </div>
        ) : null}
        {statusMessage ? (
          <div className={`status-message ${statusTone === 'error' ? 'error' : ''}`} role="status">
            {statusMessage}
          </div>
        ) : null}
        {uploadErrors.length > 0 ? renderIssues(uploadErrors, 'error') : null}

        <div className="upload-actions">
          <button type="button" className="button secondary" onClick={handleBack}>
            Back to dashboards
          </button>
          <div className="upload-actions__right">
            {hasStoredUploads ? (
              <button type="button" className="button tertiary" onClick={handleToggleActive}>
                {uploadedActive ? 'Pause uploaded data' : 'Use uploaded data'}
              </button>
            ) : null}
            <button
              type="button"
              className="button primary"
              onClick={handleApply}
              disabled={!hasUploads || parsedErrors > 0 || parsedRowsCount === 0 || isSubmitting}
            >
              {isSubmitting ? 'Uploading…' : 'Apply to dashboards'}
            </button>
            {hasStoredUploads ? (
              <button
                type="button"
                className="button tertiary"
                onClick={handleClearUploads}
                disabled={isSubmitting}
              >
                Clear uploads
              </button>
            ) : null}
          </div>
        </div>

        {!hasUploads ? (
          <EmptyState
            icon={<UploadIcon />}
            title="No CSVs uploaded yet"
            message="Upload campaign metrics to begin. Parish and budget CSVs are optional."
            actionLabel="Back to dashboards"
            actionVariant="secondary"
            onAction={handleBack}
          />
        ) : null}
      </section>
    </div>
  );
};

export default CsvUpload;
