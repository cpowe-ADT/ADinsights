import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import DashboardState from '../components/DashboardState';
import GovernedWidgetRenderer from '../components/reporting/GovernedWidgetRenderer';
import SkeletonLoader from '../components/SkeletonLoader';
import {
  createReportExport,
  downloadReportExport,
  fetchReportDiagnostics,
  getReport,
  listReportExports,
  previewReport,
  runScheduledReportDryRun,
  toggleReportSchedule,
  updateReport,
  updateReportSchedule,
  type ReportDefinition,
  type ReportDiagnosticsResponse,
  type ReportExportJob,
  type ReportPreviewResponse,
} from '../lib/phase2Api';
import { saveBlobAsFile } from '../lib/download';
import { formatAbsoluteTime, formatRelativeTime } from '../lib/format';
import { useToastStore } from '../stores/useToastStore';
import '../styles/phase2.css';
import '../styles/dashboard.css';
import '../styles/skeleton.css';

const exportFormats: Array<'csv' | 'pdf' | 'png'> = ['csv', 'pdf', 'png'];

function isReportV1(report: ReportDefinition | null): boolean {
  return report?.layout?.schema_version === 'report.v1';
}

function objectValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function latestSnapshot(exports: ReportExportJob[]): Record<string, unknown> {
  for (const job of exports) {
    const metadata = objectValue(job.metadata);
    const reportPreview = objectValue(metadata.report_preview);
    const snapshot = objectValue(reportPreview.report_snapshot);
    if (Object.keys(snapshot).length > 0) {
      return {
        ...snapshot,
        delivery_status: metadata.delivery_status ?? reportPreview.delivery_status,
      };
    }
  }
  return {};
}

type CoverageDatasetSummary = ReportPreviewResponse['coverage_summary']['datasets'][number];

const failedCoverageStatuses = new Set([
  'missing_history',
  'not_previously_synced',
  'permission_missing',
  'unsupported_metric',
]);

const warningCoverageStatuses = new Set(['stale', 'partial', 'source_disconnected']);

const numberFormatter = new Intl.NumberFormat('en-US');

function coverageStatuses(dataset: CoverageDatasetSummary): string[] {
  return Object.entries(dataset.statuses ?? {})
    .filter(([, count]) => Number(count) > 0)
    .map(([status]) => status);
}

function coverageSummaryStatus(dataset: CoverageDatasetSummary): string {
  const statuses = coverageStatuses(dataset);
  return (
    statuses.find((status) => failedCoverageStatuses.has(status)) ??
    statuses.find((status) => warningCoverageStatuses.has(status)) ??
    statuses[0] ??
    'unknown'
  );
}

function coverageSummaryTone(dataset: CoverageDatasetSummary): 'fresh' | 'stale' | 'failed' {
  const status = coverageSummaryStatus(dataset);
  if (status === 'fresh') return 'fresh';
  if (warningCoverageStatuses.has(status)) return 'stale';
  return 'failed';
}

function exportReadiness(preview: ReportPreviewResponse): {
  label: 'export ready' | 'export with warnings' | 'export blocked';
  tone: 'fresh' | 'stale' | 'failed';
} {
  if (!preview.export_ready) {
    return { label: 'export blocked', tone: 'failed' };
  }
  const hasCoverageWarnings = preview.coverage_summary.datasets.some(
    (dataset) => coverageSummaryStatus(dataset) !== 'fresh',
  );
  return hasCoverageWarnings
    ? { label: 'export with warnings', tone: 'stale' }
    : { label: 'export ready', tone: 'fresh' };
}

function sourceHealthTone(value: boolean): 'fresh' | 'failed' {
  return value ? 'fresh' : 'failed';
}

function datasetLabel(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function reportDateRangeLabel(
  report: ReportDefinition | null,
  preview: ReportPreviewResponse | null,
): string {
  const previewRange = objectValue(preview?.date_range);
  const reportFilters = objectValue(report?.filters);
  const start = String(previewRange.start_date ?? reportFilters.start_date ?? '');
  const end = String(previewRange.end_date ?? reportFilters.end_date ?? '');
  if (start && end) {
    return `${start} to ${end}`;
  }
  const range = String(previewRange.date_range ?? reportFilters.date_range ?? '');
  return range ? range.replace(/_/g, ' ') : 'Date range not set';
}

function metaSetupPath(reportId?: string): string {
  if (!reportId) {
    return '/dashboards/data-sources?sources=social';
  }
  return `/dashboards/data-sources?sources=social&returnTo=${encodeURIComponent(`/reports/${reportId}`)}`;
}

function storedRowCount(
  sourceHealth: ReportDiagnosticsResponse['source_health'],
  key: string,
): string {
  const rows = objectValue(sourceHealth?.stored_rows);
  const row = objectValue(rows[key]);
  const count = row.row_count;
  return typeof count === 'number' ? numberFormatter.format(count) : '0';
}

const ReportClientHero = ({
  report,
  preview,
  diagnostics,
}: {
  report: ReportDefinition;
  preview: ReportPreviewResponse | null;
  diagnostics: ReportDiagnosticsResponse | null;
}) => {
  const readiness = preview ? exportReadiness(preview) : null;
  const sourceHealth = diagnostics?.source_health;
  const needsMeta = sourceHealth ? !sourceHealth.meta_credentials.has_valid_credential : false;
  return (
    <section className="report-client-hero" aria-label="Report cover summary">
      <div className="report-client-hero__copy">
        <p className="dashboardEyebrow">Client report</p>
        <h2>{report.name}</h2>
        <p>
          {report.description ||
            'Monthly social reporting powered by governed ADinsights widgets and stored aggregate data.'}
        </p>
        <div className="report-client-hero__meta" aria-label="Report metadata">
          <span>{reportDateRangeLabel(report, preview)}</span>
          <span>{preview?.report.catalog_schema_version ?? 'Catalog pending'}</span>
          <span>
            {preview ? `Generated ${formatRelativeTime(preview.generated_at)}` : 'Preview loading'}
          </span>
        </div>
      </div>
      <div className="report-client-hero__aside">
        <span className={`phase2-pill phase2-pill--${readiness?.tone ?? 'stale'}`}>
          {readiness?.label ?? 'loading preview'}
        </span>
        <div className="report-client-hero__stats">
          <div>
            <span>Pages</span>
            <strong>{preview?.pages.length ?? '-'}</strong>
          </div>
          <div>
            <span>Datasets</span>
            <strong>{preview?.coverage_summary.datasets.length ?? '-'}</strong>
          </div>
          <div>
            <span>Preview hash</span>
            <strong>{preview?.preview_hash ? preview.preview_hash.slice(0, 8) : '-'}</strong>
          </div>
        </div>
        {needsMeta ? (
          <Link className="button primary" to={metaSetupPath(report.id)}>
            Open Meta setup
          </Link>
        ) : null}
      </div>
    </section>
  );
};

const ReportReadinessHero = ({
  preview,
  diagnostics,
}: {
  preview: ReportPreviewResponse | null;
  diagnostics: ReportDiagnosticsResponse | null;
}) => {
  if (!preview && !diagnostics) {
    return null;
  }
  const sourceHealth = diagnostics?.source_health;
  const storedOnly = sourceHealth?.stored_aggregate_only !== false;
  const noLiveProviderCalls = sourceHealth?.no_live_provider_calls !== false;
  const isExportReady = Boolean(preview?.export_ready && diagnostics?.export_ready);
  const hasValidMetaCredential = Boolean(sourceHealth?.meta_credentials.has_valid_credential);
  const readinessCopy = isExportReady
    ? 'The report is using stored aggregate data and can be exported for review.'
    : hasValidMetaCredential
      ? 'The report shell renders, but this report range is missing stored rows. Run the fixed-range backfill before using it as a client-ready report.'
      : 'The report shell renders, but source data coverage is incomplete. Reconnect Meta, then run the fixed-range backfill before using it as a client-ready report.';
  const blockerItems =
    preview?.blocking_reasons.length || diagnostics?.blocking_reasons.length
      ? Array.from(
          new Set([...(preview?.blocking_reasons ?? []), ...(diagnostics?.blocking_reasons ?? [])]),
        )
      : [];
  const nextActions = sourceHealth?.recommended_next_actions ?? [];
  const rowItems = [
    ['Paid Meta Ads', 'paid_meta_ads'],
    ['Organic Page', 'organic_facebook_page'],
    ['Top Posts', 'organic_facebook_posts'],
    ['Content Ops', 'content_ops'],
  ] as const;

  return (
    <section
      className={`reporting-status-hero reporting-status-hero--${isExportReady ? 'ready' : 'blocked'}`}
    >
      <div className="reporting-status-hero__main">
        <p className="dashboardEyebrow">Report data readiness</p>
        <div className="reporting-status-hero__headline">
          <h2>{isExportReady ? 'Ready to export' : 'Needs source data'}</h2>
          <span className={`phase2-pill phase2-pill--${isExportReady ? 'fresh' : 'failed'}`}>
            {isExportReady ? 'export ready' : 'export blocked'}
          </span>
        </div>
        <p>{readinessCopy}</p>
        <div className="reporting-status-hero__facts" aria-label="Report safety facts">
          <span className={`phase2-pill phase2-pill--${storedOnly ? 'fresh' : 'failed'}`}>
            stored aggregate data
          </span>
          <span className={`phase2-pill phase2-pill--${noLiveProviderCalls ? 'fresh' : 'failed'}`}>
            no live provider calls
          </span>
          <span
            className={`phase2-pill phase2-pill--${hasValidMetaCredential ? 'fresh' : 'failed'}`}
          >
            {hasValidMetaCredential ? 'Meta connected' : 'Meta reauth needed'}
          </span>
        </div>
      </div>

      <div className="reporting-status-hero__side">
        <h3>Stored source rows</h3>
        <p className="phase2-note">
          Source-health counts; preview blockers still decide export readiness.
        </p>
        <div className="reporting-status-hero__rows">
          {rowItems.map(([label, key]) => (
            <div className="reporting-source-row" key={key}>
              <span>{label}</span>
              <strong>{storedRowCount(sourceHealth, key)}</strong>
            </div>
          ))}
        </div>
      </div>

      <div className="reporting-status-hero__work">
        <div>
          <h3>Blocking issues</h3>
          {blockerItems.length > 0 ? (
            <ul className="reporting-action-list">
              {blockerItems.slice(0, 4).map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          ) : (
            <p className="phase2-note">No blocking coverage issues in the current preview.</p>
          )}
        </div>
        <div>
          <h3>Fix next</h3>
          {nextActions.length > 0 ? (
            <ul className="reporting-action-list">
              {nextActions.slice(0, 4).map((action) => (
                <li key={action}>{action}</li>
              ))}
            </ul>
          ) : (
            <p className="phase2-note">No source-health actions were returned.</p>
          )}
        </div>
      </div>
    </section>
  );
};

const DataPathPanel = ({
  reportId,
  diagnostics,
}: {
  reportId: string;
  diagnostics: ReportDiagnosticsResponse | null;
}) => {
  const sourceHealth = diagnostics?.source_health;
  if (!sourceHealth) return null;

  const pageRows = storedRowCount(sourceHealth, 'organic_facebook_page');
  const postRows = storedRowCount(sourceHealth, 'organic_facebook_posts');
  const paidRows = storedRowCount(sourceHealth, 'paid_meta_ads');
  const contentRows = storedRowCount(sourceHealth, 'content_ops');
  const hasUsablePageToken =
    sourceHealth.meta_page_connection.has_usable_page_auth ??
    sourceHealth.meta_page_connection.has_active_connection;
  const pageTokenProblemCount =
    sourceHealth.meta_page_connection.unusable_page_auth_count ??
    (sourceHealth.meta_page_connection.page_auth_status_counts?.missing ?? 0) +
      (sourceHealth.meta_page_connection.page_auth_status_counts?.unreadable ?? 0);
  const steps = [
    {
      label: 'Meta OAuth',
      tone: sourceHealth.meta_credentials.has_valid_credential ? 'fresh' : 'failed',
      status: sourceHealth.meta_credentials.has_valid_credential ? 'Connected' : 'Reconnect needed',
      detail: sourceHealth.meta_credentials.has_valid_credential
        ? 'Marketing credential is available for sync/backfill.'
        : 'No valid marketing credential is available for fresh Meta reporting.',
    },
    {
      label: 'Facebook Page',
      tone: hasUsablePageToken ? 'fresh' : 'failed',
      status: hasUsablePageToken ? 'Connected' : 'Reconnect needed',
      detail: hasUsablePageToken
        ? `${sourceHealth.meta_page_connection.active_count} active Page connection record(s); ${sourceHealth.meta_page_connection.usable_page_auth_count ?? 1} usable Page authorization(s).`
        : `${sourceHealth.meta_page_connection.active_count} active Page connection record(s); ${pageTokenProblemCount} stored Page authorization(s) need reconnect.`,
    },
    {
      label: 'Stored report rows',
      tone:
        pageRows !== '0' || postRows !== '0' || paidRows !== '0' || contentRows !== '0'
          ? 'stale'
          : 'failed',
      status: 'Coverage check',
      detail: `Paid ${paidRows}; organic page ${pageRows}; posts ${postRows}; content ${contentRows}.`,
    },
    {
      label: 'Sync pipeline',
      tone: sourceHealth.meta_airbyte.active_count > 0 ? 'stale' : 'failed',
      status: sourceHealth.meta_airbyte.active_count > 0 ? 'Configured' : 'Inactive',
      detail: sourceHealth.meta_airbyte.latest_synced_at
        ? `Latest sync ${formatRelativeTime(sourceHealth.meta_airbyte.latest_synced_at)}.`
        : 'No completed Meta sync is recorded for this report path.',
    },
  ];

  return (
    <section className="report-data-path" aria-label="Report data path">
      <div className="report-data-path__intro">
        <p className="dashboardEyebrow">Data path</p>
        <h3>Make this report pull real Facebook and Meta Ads data</h3>
        <p>
          Rendering and export use stored aggregate ADinsights data. Live Meta calls belong in
          reconnect and backfill only.
        </p>
        <Link className="button secondary" to={metaSetupPath(reportId)}>
          Open Meta setup
        </Link>
      </div>
      <div className="report-data-path__steps">
        {steps.map((step) => (
          <article className="report-data-step" key={step.label}>
            <span className={`phase2-pill phase2-pill--${step.tone}`}>{step.status}</span>
            <h4>{step.label}</h4>
            <p>{step.detail}</p>
          </article>
        ))}
      </div>
    </section>
  );
};

const SnapshotPanel = ({
  preview,
  exports,
}: {
  preview: ReportPreviewResponse | null;
  exports: ReportExportJob[];
}) => {
  const snapshot = latestSnapshot(exports);
  if (Object.keys(snapshot).length === 0) {
    return null;
  }
  const snapshotHash = String(snapshot.preview_hash ?? '');
  const matchesPreview = Boolean(preview?.preview_hash && preview.preview_hash === snapshotHash);
  const deliveryStatus = objectValue(snapshot.delivery_status);
  return (
    <article className="phase2-card">
      <div className="reporting-widget__header">
        <div>
          <p className="dashboardEyebrow">Export snapshot</p>
          <h3>Reproducibility</h3>
        </div>
        <span className={`phase2-pill phase2-pill--${matchesPreview ? 'fresh' : 'stale'}`}>
          {matchesPreview ? 'matches preview' : 'differs from preview'}
        </span>
      </div>
      <div className="reporting-coverage-list">
        <div className="reporting-coverage-note">
          <span>Generated</span>
          <span>{String(snapshot.generated_at ?? 'Unknown')}</span>
        </div>
        <div className="reporting-coverage-note">
          <span>Preview hash</span>
          <span>{snapshotHash || 'Unavailable'}</span>
        </div>
        {deliveryStatus.status ? (
          <div className="reporting-coverage-note">
            <span>Delivery status</span>
            <span>{String(deliveryStatus.status)}</span>
          </div>
        ) : null}
      </div>
    </article>
  );
};

const DiagnosticsPanel = ({
  diagnostics,
  status,
}: {
  diagnostics: ReportDiagnosticsResponse | null;
  status: 'idle' | 'loading' | 'ready' | 'error';
}) => {
  if (status === 'idle') return null;
  if (status === 'loading') {
    return (
      <article className="phase2-card">
        <h3>Diagnostics</h3>
        <SkeletonLoader variant="card" count={1} />
      </article>
    );
  }
  if (status === 'error' || !diagnostics) {
    return (
      <DashboardState
        variant="error"
        layout="page"
        title="Diagnostics unavailable"
        message="Unable to load report diagnostics."
      />
    );
  }
  const sourceHealth = diagnostics.source_health;
  const metaCredentials = sourceHealth?.meta_credentials;
  const metaPageConnection = sourceHealth?.meta_page_connection;
  const metaAirbyte = sourceHealth?.meta_airbyte;
  const hasUsablePageToken =
    metaPageConnection?.has_usable_page_auth ?? Boolean(metaPageConnection?.has_active_connection);
  const pageTokenProblemCount =
    metaPageConnection?.unusable_page_auth_count ??
    (metaPageConnection?.page_auth_status_counts?.missing ?? 0) +
      (metaPageConnection?.page_auth_status_counts?.unreadable ?? 0);
  return (
    <details className="phase2-card report-diagnostics">
      <summary className="reporting-widget__header">
        <div>
          <p className="dashboardEyebrow">Support diagnostics</p>
          <h3>Stored data and delivery readiness</h3>
        </div>
        <span
          className={`phase2-pill phase2-pill--${diagnostics.export_ready ? 'fresh' : 'failed'}`}
        >
          {diagnostics.export_ready ? 'ready' : 'blocked'}
        </span>
      </summary>
      <div className="reporting-coverage-list">
        {diagnostics.datasets.map((dataset) => (
          <div className="reporting-coverage-note" key={dataset.dataset}>
            <span className={`phase2-pill phase2-pill--${dataset.coverage_status}`}>
              {dataset.coverage_status}
            </span>
            <span>
              {dataset.dataset}: {dataset.row_count} rows
              {dataset.retained_range.start_date && dataset.retained_range.end_date
                ? ` from ${dataset.retained_range.start_date} to ${dataset.retained_range.end_date}`
                : ''}
            </span>
            <span>{dataset.recommended_next_action}</span>
          </div>
        ))}
      </div>
      {diagnostics.export_history.length > 0 ? (
        <div className="reporting-coverage-list">
          <h4>Recent export evidence</h4>
          {diagnostics.export_history.slice(0, 3).map((job) => (
            <div className="reporting-coverage-note" key={job.id}>
              <span>{job.format.toUpperCase()}</span>
              <span>{job.status}</span>
              <span>{job.delivery_status || 'manual'}</span>
            </div>
          ))}
        </div>
      ) : null}
      {sourceHealth ? (
        <div className="reporting-coverage-list">
          <h4>Source health</h4>
          <div className="reporting-coverage-note">
            <span
              className={`phase2-pill phase2-pill--${sourceHealthTone(Boolean(metaCredentials?.has_valid_credential))}`}
            >
              {metaCredentials?.has_valid_credential
                ? 'meta credential valid'
                : 'meta reauth needed'}
            </span>
            <span>
              {metaCredentials?.credential_count ?? 0} Meta credential records
              {metaCredentials?.has_reauth_required ? '; reconnect required' : ''}
            </span>
          </div>
          <div className="reporting-coverage-note">
            <span className={`phase2-pill phase2-pill--${sourceHealthTone(hasUsablePageToken)}`}>
              {hasUsablePageToken ? 'page token usable' : 'page reconnect needed'}
            </span>
            <span>
              {metaPageConnection?.active_count ?? 0} active Page connection records
              {hasUsablePageToken
                ? `; ${metaPageConnection?.usable_page_auth_count ?? 1} usable Page authorization(s)`
                : `; ${pageTokenProblemCount} stored Page authorization(s) need reconnect`}
            </span>
          </div>
          <div className="reporting-coverage-note">
            <span
              className={`phase2-pill phase2-pill--${sourceHealthTone(Boolean(metaAirbyte?.active_count))}`}
            >
              {metaAirbyte?.active_count ? 'airbyte configured' : 'airbyte inactive'}
            </span>
            <span>
              {metaAirbyte?.active_count ?? 0} active Meta Airbyte connections
              {metaAirbyte?.latest_synced_at ? `; latest sync ${metaAirbyte.latest_synced_at}` : ''}
            </span>
          </div>
          <div className="reporting-coverage-note">
            <span>Stored rows</span>
            <span>
              paid {storedRowCount(sourceHealth, 'paid_meta_ads')}; organic page{' '}
              {storedRowCount(sourceHealth, 'organic_facebook_page')}; posts{' '}
              {storedRowCount(sourceHealth, 'organic_facebook_posts')}; content{' '}
              {storedRowCount(sourceHealth, 'content_ops')}
            </span>
          </div>
          {sourceHealth.recommended_next_actions.slice(0, 5).map((action) => (
            <div className="reporting-coverage-note" key={action}>
              <span>Next action</span>
              <span>{action}</span>
            </div>
          ))}
        </div>
      ) : null}
    </details>
  );
};

const ReportPreviewPanel = ({
  preview,
  status,
  error,
}: {
  preview: ReportPreviewResponse | null;
  status: 'idle' | 'loading' | 'ready' | 'error';
  error: string;
}) => {
  if (status === 'idle') {
    return null;
  }
  if (status === 'loading') {
    return (
      <article className="phase2-card">
        <h3>Report preview</h3>
        <SkeletonLoader variant="card" count={2} />
      </article>
    );
  }
  if (status === 'error' || !preview) {
    return (
      <DashboardState
        variant="error"
        layout="page"
        title="Report preview unavailable"
        message={error || 'Unable to preview report.'}
      />
    );
  }
  const readiness = exportReadiness(preview);
  return (
    <section className="reporting-report-preview">
      <article className="phase2-card reporting-preview-summary">
        <div className="reporting-widget__header">
          <div>
            <p className="dashboardEyebrow">Report preview</p>
            <h3>Coverage and export readiness</h3>
          </div>
          <span className={`phase2-pill phase2-pill--${readiness.tone}`}>{readiness.label}</span>
        </div>
        {preview.blocking_reasons.length > 0 ? (
          <ul className="reporting-widget__warnings">
            {preview.blocking_reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        ) : null}
        <div className="reporting-coverage-list">
          {preview.coverage_summary.datasets.map((dataset) => {
            const status = coverageSummaryStatus(dataset);
            return (
              <div key={dataset.dataset} className="reporting-coverage-card">
                <div>
                  <p className="reporting-coverage-card__label">{datasetLabel(dataset.dataset)}</p>
                  <p className="phase2-note">
                    {dataset.row_count} rows retained
                    {dataset.covered_start_date && dataset.covered_end_date
                      ? ` from ${dataset.covered_start_date} to ${dataset.covered_end_date}`
                      : ''}
                  </p>
                </div>
                <span className={`phase2-pill phase2-pill--${coverageSummaryTone(dataset)}`}>
                  {status}
                </span>
                {dataset.notes.length > 0 ? (
                  <p className="reporting-coverage-card__note">{dataset.notes[0]}</p>
                ) : null}
              </div>
            );
          })}
        </div>
      </article>

      <div className="reporting-report-pages" aria-label="Rendered report pages">
        {preview.pages.map((page) => (
          <section className="reporting-report-page" key={page.id} aria-label={page.title}>
            <header className="reporting-report-page__header">
              <p className="dashboardEyebrow">Report page</p>
              <h2>{page.title}</h2>
            </header>
            <div className="reporting-report-page__body">
              {page.sections.map((section) => (
                <div className="reporting-grid" key={section.id}>
                  {section.widgets.map((widget) => (
                    <GovernedWidgetRenderer key={widget.widget_id} widget={widget} />
                  ))}
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>
    </section>
  );
};

const ReportDetailPage = () => {
  const { reportId } = useParams<{ reportId: string }>();
  const addToast = useToastStore((s) => s.addToast);
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [report, setReport] = useState<ReportDefinition | null>(null);
  const [exports, setExports] = useState<ReportExportJob[]>([]);
  const [preview, setPreview] = useState<ReportPreviewResponse | null>(null);
  const [previewStatus, setPreviewStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>(
    'idle',
  );
  const [diagnostics, setDiagnostics] = useState<ReportDiagnosticsResponse | null>(null);
  const [diagnosticsStatus, setDiagnosticsStatus] = useState<
    'idle' | 'loading' | 'ready' | 'error'
  >('idle');
  const [previewError, setPreviewError] = useState('');
  const [error, setError] = useState<string>('Unable to load report.');
  const [creatingFormat, setCreatingFormat] = useState<string | null>(null);
  const [runningDryRun, setRunningDryRun] = useState(false);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [scheduleCron, setScheduleCron] = useState('');
  const [scheduleEmails, setScheduleEmails] = useState('');
  const [savingSchedule, setSavingSchedule] = useState(false);

  // Inline editing state
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [saving, setSaving] = useState(false);

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
      setPreview(null);
      setDiagnostics(null);
      if (reportPayload.layout?.schema_version === 'report.v1') {
        setPreviewStatus('loading');
        setDiagnosticsStatus('loading');
        try {
          const [previewPayload, diagnosticsPayload] = await Promise.all([
            previewReport(reportId),
            fetchReportDiagnostics(reportId),
          ]);
          setPreview(previewPayload);
          setDiagnostics(diagnosticsPayload);
          setPreviewStatus('ready');
          setDiagnosticsStatus('ready');
          setPreviewError('');
        } catch (previewLoadError) {
          setPreviewStatus('error');
          setDiagnosticsStatus('error');
          setPreviewError(
            previewLoadError instanceof Error
              ? previewLoadError.message
              : 'Unable to preview report.',
          );
        }
      } else {
        setPreviewStatus('idle');
        setDiagnosticsStatus('idle');
      }
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
        addToast('Export requested');
        await load();
      } catch (exportError) {
        addToast(
          exportError instanceof Error ? exportError.message : 'Export request failed',
          'error',
        );
      } finally {
        setCreatingFormat(null);
      }
    },
    [addToast, load, reportId],
  );

  const runDryRun = useCallback(async () => {
    if (!reportId) return;
    setRunningDryRun(true);
    try {
      const job = await runScheduledReportDryRun(reportId, 'pdf');
      addToast(
        job.status === 'failed'
          ? 'Scheduled dry-run blocked; see diagnostics'
          : 'Scheduled dry-run queued',
        job.status === 'failed' ? 'error' : 'success',
      );
      await load();
    } catch (dryRunError) {
      addToast(
        dryRunError instanceof Error ? dryRunError.message : 'Scheduled dry-run failed',
        'error',
      );
    } finally {
      setRunningDryRun(false);
    }
  }, [addToast, load, reportId]);

  const downloadExport = useCallback(
    async (job: ReportExportJob) => {
      setDownloadingId(job.id);
      try {
        const { blob, filename } = await downloadReportExport(job.id);
        saveBlobAsFile(blob, filename);
      } catch {
        addToast('Export download failed', 'error');
      } finally {
        setDownloadingId(null);
      }
    },
    [addToast],
  );

  useEffect(() => {
    if (report) {
      setScheduleCron(report.schedule_cron);
      setScheduleEmails(report.delivery_emails.join(', '));
    }
  }, [report]);

  const handleToggleSchedule = useCallback(
    async (enabled: boolean) => {
      if (!reportId) return;
      await toggleReportSchedule(reportId, enabled);
      await load();
    },
    [load, reportId],
  );

  const handleSaveSchedule = useCallback(async () => {
    if (!reportId) return;
    setSavingSchedule(true);
    try {
      await updateReportSchedule(reportId, {
        schedule_cron: scheduleCron,
        delivery_emails: scheduleEmails
          .split(',')
          .map((e) => e.trim())
          .filter(Boolean),
      });
      await load();
    } finally {
      setSavingSchedule(false);
    }
  }, [load, reportId, scheduleCron, scheduleEmails]);

  if (state === 'loading') {
    return (
      <section className="phase2-page">
        <header className="phase2-page__header">
          <div>
            <p className="dashboardEyebrow">Reporting</p>
            <h1 className="dashboardHeading">Report Detail</h1>
          </div>
        </header>
        <SkeletonLoader variant="card" count={2} />
        <SkeletonLoader variant="table" />
      </section>
    );
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

  const reportActionsBlocked =
    isReportV1(report) &&
    (previewStatus !== 'ready' ||
      diagnosticsStatus !== 'ready' ||
      preview?.export_ready !== true ||
      diagnostics?.export_ready !== true);

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
                Edit report details
              </button>
              <button type="button" className="button secondary" onClick={() => void load()}>
                Refresh report status
              </button>
            </>
          )}
        </div>
      </header>

      {isReportV1(report) ? (
        <>
          <ReportClientHero report={report} preview={preview} diagnostics={diagnostics} />
          <ReportReadinessHero preview={preview} diagnostics={diagnostics} />
          <DataPathPanel reportId={report.id} diagnostics={diagnostics} />
          <ReportPreviewPanel preview={preview} status={previewStatus} error={previewError} />
          <SnapshotPanel preview={preview} exports={exports} />
          <DiagnosticsPanel diagnostics={diagnostics} status={diagnosticsStatus} />
        </>
      ) : null}

      <section className="reporting-ops-grid" aria-label="Report operations">
        <article className="phase2-card reporting-ops-panel">
          <div>
            <p className="dashboardEyebrow">Exports</p>
            <h3>Export actions</h3>
          </div>
          <p className="phase2-note">
            Generate CSV, PDF, or PNG exports for this report.
            {isReportV1(report) && preview && !preview.export_ready
              ? ' Export is blocked until coverage issues are resolved.'
              : ''}
          </p>
          <div className="phase2-row-actions">
            {exportFormats.map((format) => (
              <button
                key={format}
                type="button"
                className="button secondary"
                onClick={() => void requestExport(format)}
                disabled={creatingFormat !== null || reportActionsBlocked}
              >
                {creatingFormat === format
                  ? `Generating ${format.toUpperCase()}…`
                  : `Generate ${format.toUpperCase()} export`}
              </button>
            ))}
          </div>
        </article>

        <article className="phase2-card reporting-ops-panel">
          <div>
            <p className="dashboardEyebrow">Delivery</p>
            <h3>Scheduled delivery</h3>
          </div>
          <p className="phase2-note">Configure automated report delivery via email.</p>
          <div className="phase2-row-actions reporting-schedule-toggle">
            <label>
              <input
                type="checkbox"
                checked={report.schedule_enabled}
                onChange={(e) => void handleToggleSchedule(e.target.checked)}
              />{' '}
              Enable schedule
            </label>
          </div>
          {report.schedule_enabled && (
            <div className="phase2-form">
              <label className="phase2-form__field">
                <span>Cron expression</span>
                <input
                  type="text"
                  value={scheduleCron}
                  onChange={(e) => setScheduleCron(e.target.value)}
                  placeholder="0 8 * * 1"
                />
                <span className="phase2-note">e.g. &quot;0 8 * * 1&quot; = 8 AM every Monday</span>
              </label>
              <label className="phase2-form__field">
                <span>Delivery emails (comma-separated)</span>
                <input
                  type="text"
                  value={scheduleEmails}
                  onChange={(e) => setScheduleEmails(e.target.value)}
                  placeholder="team@example.com, boss@example.com"
                />
              </label>
              <div className="phase2-row-actions">
                <button
                  type="button"
                  className="button primary"
                  onClick={() => void handleSaveSchedule()}
                  disabled={savingSchedule}
                >
                  {savingSchedule ? 'Saving\u2026' : 'Save schedule'}
                </button>
                {isReportV1(report) ? (
                  <button
                    type="button"
                    className="button secondary"
                    onClick={() => void runDryRun()}
                    disabled={runningDryRun || reportActionsBlocked}
                  >
                    {runningDryRun ? 'Testing scheduled delivery...' : 'Test scheduled delivery'}
                  </button>
                ) : null}
              </div>
            </div>
          )}
          {report.last_scheduled_at && (
            <p className="phase2-note">
              Last scheduled: {formatRelativeTime(report.last_scheduled_at)} (
              {formatAbsoluteTime(report.last_scheduled_at)})
            </p>
          )}
        </article>
      </section>

      {exports.length === 0 ? (
        <DashboardState
          variant="empty"
          layout="page"
          title="No export jobs yet"
          message="Request an export to begin tracking job progress."
        />
      ) : (
        <div className="phase2-table-wrap">
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
                      <button
                        type="button"
                        className="button tertiary"
                        disabled={downloadingId === job.id}
                        onClick={() => void downloadExport(job)}
                      >
                        {downloadingId === job.id ? 'Downloading...' : 'Download'}
                      </button>
                    ) : (
                      'Pending'
                    )}
                    {job.error_message ? <div>{job.error_message}</div> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
};

export default ReportDetailPage;
