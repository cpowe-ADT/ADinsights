import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import DashboardState from '../components/DashboardState';
import SkeletonLoader from '../components/SkeletonLoader';
import {
  createSlbMonthlyReportTemplate,
  fetchReportDataAvailability,
  listReports,
  type ReportDataAvailabilityResponse,
  type ReportDefinition,
} from '../lib/phase2Api';
import { formatAbsoluteTime, formatRelativeTime } from '../lib/format';
import { canAccessCreatorUi } from '../lib/rbac';
import '../styles/phase2.css';
import '../styles/dashboard.css';
import '../styles/skeleton.css';

const SLB_TEMPLATE_KEY = 'slb_monthly_social_report';

function reportTemplateKey(report: ReportDefinition): string {
  const filters = report.filters as Record<string, unknown> | undefined;
  const layout = report.layout as Record<string, unknown> | undefined;
  return String(filters?.template_key ?? layout?.template_key ?? '');
}

function isSlbReport(report: ReportDefinition): boolean {
  return reportTemplateKey(report) === SLB_TEMPLATE_KEY;
}

const availabilityDatasetOrder = [
  'paid_meta_ads',
  'organic_facebook_page',
  'organic_facebook_posts',
  'content_ops',
];

function availabilityTone(status: string): 'fresh' | 'stale' | 'failed' {
  if (status === 'fresh') return 'fresh';
  if (status === 'partial' || status === 'stale' || status === 'source_disconnected') {
    return 'stale';
  }
  return 'failed';
}

function formatDatasetName(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

const ReportAvailabilityPanel = ({
  availability,
  error,
  existingSlbReport,
}: {
  availability: ReportDataAvailabilityResponse | null;
  error: string;
  existingSlbReport: ReportDefinition | undefined;
}) => {
  if (!availability && !error) return null;
  return (
    <section className="phase2-card report-availability-panel">
      <div className="reporting-widget__header">
        <div>
          <p className="dashboardEyebrow">Report data readiness</p>
          <h3>SLB report source availability</h3>
          <p className="phase2-note">
            Stored rows for {availability?.requested.start_date ?? 'the selected range'} to{' '}
            {availability?.requested.end_date ?? 'the selected range'}.
          </p>
        </div>
        {availability ? (
          <span
            className={`phase2-pill phase2-pill--${
              availability.eligible_for_report_export ? 'fresh' : 'failed'
            }`}
          >
            {availability.eligible_for_report_export ? 'ready' : 'blocked'}
          </span>
        ) : null}
      </div>
      {error ? <p className="phase2-note">{error}</p> : null}
      {availability ? (
        <>
          <div className="reporting-coverage-list">
            {availabilityDatasetOrder.map((datasetKey) => {
              const dataset = availability.datasets[datasetKey];
              if (!dataset) return null;
              return (
                <div className="reporting-coverage-card" key={datasetKey}>
                  <div>
                    <p className="reporting-coverage-card__label">
                      {dataset.label || formatDatasetName(dataset.dataset)}
                    </p>
                    <p className="phase2-note">
                      {dataset.row_count} rows
                      {dataset.post_count !== undefined ? `; ${dataset.post_count} posts` : ''}
                      {dataset.published_post_count !== undefined
                        ? `; ${dataset.published_post_count} published posts`
                        : ''}
                      {dataset.min_date && dataset.max_date
                        ? ` from ${dataset.min_date} to ${dataset.max_date}`
                        : ''}
                    </p>
                  </div>
                  <span
                    className={`phase2-pill phase2-pill--${availabilityTone(dataset.coverage_status)}`}
                  >
                    {dataset.coverage_status}
                  </span>
                  <p className="reporting-coverage-card__note">{dataset.coverage_note}</p>
                </div>
              );
            })}
          </div>
          <div className="phase2-row-actions">
            {existingSlbReport ? (
              <Link to={`/reports/${existingSlbReport.id}`} className="button primary">
                Open SLB report
              </Link>
            ) : null}
            <Link to="/dashboards/data-sources?sources=social" className="button secondary">
              Check Meta data sources
            </Link>
          </div>
        </>
      ) : null}
    </section>
  );
};

const ReportsPage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const canCreate = canAccessCreatorUi(user);
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [reports, setReports] = useState<ReportDefinition[]>([]);
  const [error, setError] = useState('Unable to load reports.');
  const [availability, setAvailability] = useState<ReportDataAvailabilityResponse | null>(null);
  const [availabilityError, setAvailabilityError] = useState('');
  const [showInternal, setShowInternal] = useState(false);
  const [creatingSlb, setCreatingSlb] = useState(false);

  const load = useCallback(async () => {
    setState('loading');
    try {
      const [reportsResult, availabilityResult] = await Promise.allSettled([
        listReports(),
        fetchReportDataAvailability({
          template_key: SLB_TEMPLATE_KEY,
          date_range: 'last_month',
        }),
      ]);
      if (reportsResult.status === 'rejected') {
        throw reportsResult.reason;
      }
      setReports(reportsResult.value);
      if (availabilityResult.status === 'fulfilled') {
        setAvailability(availabilityResult.value);
        setAvailabilityError('');
      } else {
        setAvailability(null);
        setAvailabilityError(
          availabilityResult.reason instanceof Error
            ? availabilityResult.reason.message
            : 'Unable to load report data availability.',
        );
      }
      setState('ready');
    } catch (err) {
      setState('error');
      setError(err instanceof Error ? err.message : 'Unable to load reports.');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const visibleReports = useMemo(() => {
    const filtered = showInternal
      ? reports
      : reports.filter((report) => {
          const filters = report.filters as Record<string, unknown> | undefined;
          if (filters && filters.internal === true) {
            return false;
          }
          if (typeof report.name === 'string' && report.name.startsWith('internal:')) {
            return false;
          }
          return true;
        });
    return [...filtered].sort(
      (left, right) => Number(isSlbReport(right)) - Number(isSlbReport(left)),
    );
  }, [reports, showInternal]);

  const existingSlbReport = useMemo(
    () => visibleReports.find((report) => isSlbReport(report)),
    [visibleReports],
  );

  const createSlbReport = useCallback(async () => {
    setCreatingSlb(true);
    try {
      const report = await createSlbMonthlyReportTemplate({
        name: 'SLB Monthly Social Report',
        date_range: 'last_month',
      });
      navigate(`/reports/${report.id}`);
    } finally {
      setCreatingSlb(false);
    }
  }, [navigate]);

  if (state === 'loading') {
    return (
      <section className="phase2-page">
        <header className="phase2-page__header">
          <div>
            <p className="dashboardEyebrow">Reporting</p>
            <h1 className="dashboardHeading">Reports</h1>
          </div>
        </header>
        <SkeletonLoader variant="table" />
      </section>
    );
  }

  if (state === 'error') {
    return (
      <DashboardState
        variant="error"
        layout="page"
        title="Reports unavailable"
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
          <h1 className="dashboardHeading">Reports</h1>
          <p className="phase2-page__subhead">Manage saved report definitions and export jobs.</p>
        </div>
        <div className="phase2-row-actions">
          <label
            className="meta-toggle-all"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}
          >
            <input
              type="checkbox"
              checked={showInternal}
              onChange={(event) => setShowInternal(event.target.checked)}
            />
            <span>Show internal</span>
          </label>
          <button type="button" className="button secondary" onClick={() => void load()}>
            Refresh
          </button>
          {canCreate ? (
            <>
              {existingSlbReport ? (
                <Link to={`/reports/${existingSlbReport.id}`} className="button primary">
                  Open SLB report
                </Link>
              ) : (
                <button
                  type="button"
                  className="button secondary"
                  onClick={() => void createSlbReport()}
                  disabled={creatingSlb}
                >
                  {creatingSlb ? 'Creating SLB report...' : 'Create SLB monthly report'}
                </button>
              )}
              <Link to="/reports/new" className="button primary">
                New report
              </Link>
            </>
          ) : null}
        </div>
      </header>

      <ReportAvailabilityPanel
        availability={availability}
        error={availabilityError}
        existingSlbReport={existingSlbReport}
      />

      {visibleReports.length === 0 ? (
        <DashboardState
          variant="empty"
          layout="page"
          title="No reports yet"
          message="Create your first report definition to unlock exports and scheduling."
          actionLabel={canCreate ? 'Start SLB report' : undefined}
          onAction={canCreate ? () => void createSlbReport() : undefined}
        />
      ) : (
        <div className="phase2-grid">
          {visibleReports.map((report) => (
            <article className="phase2-card" key={report.id}>
              <h3>{report.name}</h3>
              <p>{report.description || 'No description provided.'}</p>
              <p className="phase2-note">
                Updated {formatRelativeTime(report.updated_at)} (
                {formatAbsoluteTime(report.updated_at)})
              </p>
              <div className="phase2-row-actions">
                <span
                  className={`phase2-pill phase2-pill--${report.is_active ? 'fresh' : 'inactive'}`}
                >
                  {report.is_active ? 'active' : 'inactive'}
                </span>
                {report.schedule_enabled ? (
                  <span className="phase2-pill phase2-pill--fresh">Scheduled</span>
                ) : null}
                <Link to={`/reports/${report.id}`} className="button tertiary">
                  {isSlbReport(report) ? 'Open SLB report' : 'Open report'}
                </Link>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
};

export default ReportsPage;
