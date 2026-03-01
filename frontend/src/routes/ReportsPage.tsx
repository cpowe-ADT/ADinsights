import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import DashboardState from '../components/DashboardState';
import { listReports, type ReportDefinition } from '../lib/phase2Api';
import { formatAbsoluteTime, formatRelativeTime } from '../lib/format';
import '../styles/phase2.css';
import '../styles/dashboard.css';

const ReportsPage = () => {
  const navigate = useNavigate();
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [reports, setReports] = useState<ReportDefinition[]>([]);
  const [error, setError] = useState('Unable to load reports.');
  const [showInternal, setShowInternal] = useState(false);

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
    if (showInternal) {
      return reports;
    }
    return reports.filter((report) => {
      const filters = report.filters as Record<string, unknown> | undefined;
      if (filters && filters.internal === true) {
        return false;
      }
      if (typeof report.name === 'string' && report.name.startsWith('internal:')) {
        return false;
      }
      return true;
    });
  }, [reports, showInternal]);

  if (state === 'loading') {
    return <DashboardState variant="loading" layout="page" message="Loading reports…" />;
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
          <label className="meta-toggle-all" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
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
          <Link to="/reports/new" className="button primary">
            New report
          </Link>
        </div>
      </header>

      {visibleReports.length === 0 ? (
        <DashboardState
          variant="empty"
          layout="page"
          title="No reports yet"
          message="Create your first report definition to unlock exports and scheduling."
          actionLabel="Create report"
          onAction={() => navigate('/reports/new')}
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
                <Link to={`/reports/${report.id}`} className="button tertiary">
                  Open
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
