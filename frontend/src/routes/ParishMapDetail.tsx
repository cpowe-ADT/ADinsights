import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

import ParishMap from '../components/ParishMap';

const ParishMapDetail = () => {
  const navigate = useNavigate();
  const handleBack = useCallback(() => {
    if (window.history.length > 1) {
      navigate(-1);
      return;
    }
    navigate('/dashboards/campaigns');
  }, [navigate]);

  return (
    <div className="dashboard-grid single-panel">
      <section className="panel full-width">
        <header className="panel-header">
          <h2>Parish heatmap</h2>
          <p className="muted">Explore the choropleth in a focused, full-width view.</p>
          <button type="button" className="button tertiary" onClick={handleBack}>
            Back to dashboard
          </button>
        </header>
        <ParishMap height={520} />
      </section>
    </div>
  );
};

export default ParishMapDetail;
