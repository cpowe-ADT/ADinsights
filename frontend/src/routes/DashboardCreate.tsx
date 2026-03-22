import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import DashboardState from '../components/DashboardState';
import { canAccessCreatorUi } from '../lib/rbac';

const DashboardCreate = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const canCreate = canAccessCreatorUi(user);

  const handleStartCampaigns = useCallback(() => {
    navigate('/dashboards/campaigns');
  }, [navigate]);

  const handleConnectSources = useCallback(() => {
    navigate('/dashboards/data-sources');
  }, [navigate]);

  const handleUploadCsv = useCallback(() => {
    navigate('/dashboards/uploads');
  }, [navigate]);

  if (!canCreate) {
    return (
      <DashboardState
        variant="empty"
        layout="page"
        title="Read-only dashboard access"
        message="Viewer access can browse dashboards, but cannot create new ones."
        actionLabel="Back to library"
        onAction={() => navigate('/dashboards')}
      />
    );
  }

  return (
    <div className="dashboard-grid single-panel">
      <section className="panel full-width">
        <header className="panel-header">
          <div className="panel-header__title-row">
            <h2>Create a dashboard</h2>
          </div>
          <p className="muted">Start with a template or connect new data to build your report.</p>
        </header>
        <div className="chart-card__actions">
          <button type="button" className="button primary" onClick={handleStartCampaigns}>
            Start with campaign dashboard
          </button>
          <button type="button" className="button secondary" onClick={handleConnectSources}>
            Connect data sources
          </button>
          <button type="button" className="button tertiary" onClick={handleUploadCsv}>
            Upload CSV
          </button>
        </div>
      </section>
    </div>
  );
};

export default DashboardCreate;
