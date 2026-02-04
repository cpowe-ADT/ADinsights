import { useCallback } from 'react';

import EmptyState from '../components/EmptyState';

const DataSourcesIcon = () => (
  <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="2.2">
    <rect x="8" y="10" width="32" height="26" rx="4" />
    <path d="M14 18h20" strokeLinecap="round" />
    <path d="M14 24h14" strokeLinecap="round" />
    <path d="M14 30h10" strokeLinecap="round" />
    <circle cx="34" cy="30" r="3.5" />
  </svg>
);

const DataSources = () => {
  const docsUrl =
    import.meta.env.VITE_DOCS_URL?.trim() ||
    'https://github.com/cpowe-ADT/ADinsights/blob/main/docs/ops/doc-index.md';

  const handleViewDocs = useCallback(() => {
    if (typeof window !== 'undefined') {
      window.open(docsUrl, '_blank', 'noopener,noreferrer');
    }
  }, [docsUrl]);

  return (
    <div className="dashboard-grid single-panel">
      <section className="panel full-width">
        <EmptyState
          icon={<DataSourcesIcon />}
          title="Connect your data sources"
          message="Source configuration lives in Airbyte and the operations runbook. Use the setup guide to connect Meta and Google Ads."
          actionLabel="Open setup guide"
          actionVariant="secondary"
          onAction={handleViewDocs}
        />
      </section>
    </div>
  );
};

export default DataSources;
