import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import DashboardState from '../components/DashboardState';
import SkeletonLoader from '../components/SkeletonLoader';
import {
  createSlbMonthlyReportTemplate,
  listReports,
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

const ReportsPage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const canCreate = canAccessCreatorUi(user);
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [reports, setReports] = useState<ReportDefinition[]>([]);
  const [error, setError] = useState('Unable to load reports.');
  const [showInternal, setShowInternal] = useState(false);
  const [creatingSlb, setCreatingSlb] = useState(false);

  const load = useCallback(async () => {
    setState('loading');
    try {
      const data = await listReports();
      setReports(data);
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
