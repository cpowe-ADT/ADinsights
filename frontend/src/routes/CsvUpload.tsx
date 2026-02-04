import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

import EmptyState from '../components/EmptyState';

const UploadIcon = () => (
  <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="2.2">
    <rect x="10" y="10" width="28" height="28" rx="4" />
    <path d="M24 30V18" strokeLinecap="round" />
    <path d="M19 22l5-5 5 5" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M16 34h16" strokeLinecap="round" />
  </svg>
);

const CsvUpload = () => {
  const navigate = useNavigate();

  const handleBack = useCallback(() => {
    navigate('/dashboards/campaigns');
  }, [navigate]);

  return (
    <div className="dashboard-grid single-panel">
      <section className="panel full-width">
        <EmptyState
          icon={<UploadIcon />}
          title="CSV uploads are coming soon"
          message="Manual uploads will appear here once the ingestion pipeline is ready."
          actionLabel="Back to dashboards"
          actionVariant="secondary"
          onAction={handleBack}
        />
      </section>
    </div>
  );
};

export default CsvUpload;
