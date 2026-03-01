import { useEffect, useState } from 'react';

import {
  createGoogleAdsExport,
  createGoogleAdsSavedView,
  fetchGoogleAdsExportStatus,
  fetchGoogleAdsSavedViews,
  type GoogleAdsExportJob,
  type GoogleAdsSavedView,
} from '../../lib/googleAdsDashboard';

const GoogleAdsReportsPage = () => {
  const [savedViews, setSavedViews] = useState<GoogleAdsSavedView[]>([]);
  const [job, setJob] = useState<GoogleAdsExportJob | null>(null);
  const [status, setStatus] = useState<'idle' | 'loading' | 'error'>('loading');
  const [error, setError] = useState('');
  const [viewName, setViewName] = useState('');

  const loadSavedViews = async () => {
    setStatus('loading');
    setError('');
    try {
      const rows = await fetchGoogleAdsSavedViews();
      setSavedViews(rows);
      setStatus('idle');
    } catch (err) {
      setStatus('error');
      setError(err instanceof Error ? err.message : 'Failed to load saved views.');
    }
  };

  useEffect(() => {
    void loadSavedViews();
  }, []);

  const handleCreateExport = async () => {
    setError('');
    try {
      const created = await createGoogleAdsExport({ export_format: 'csv', name: 'Google Ads Campaign Export' });
      setJob(created);
      if (created.id) {
        const refreshed = await fetchGoogleAdsExportStatus(created.id);
        setJob(refreshed);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create export.');
    }
  };

  const handleCreateSavedView = async () => {
    if (!viewName.trim()) {
      return;
    }
    setError('');
    try {
      await createGoogleAdsSavedView({
        name: viewName.trim(),
        description: 'Saved from Reports & Exports page',
        filters: {},
        columns: [],
        is_shared: true,
      });
      setViewName('');
      await loadSavedViews();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create saved view.');
    }
  };

  return (
    <section className="dashboardPage">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Google Ads</p>
        <h1 className="dashboardHeading">Reports & Exports</h1>
        <p className="dashboardSubtitle">Create on-demand exports and manage reusable saved views.</p>
      </header>

      {error ? (
        <div className="dashboard-state dashboard-state--page" role="alert">
          {error}
        </div>
      ) : null}

      <div className="panel" style={{ marginBottom: '1rem' }}>
        <h2>Export</h2>
        <div className="dashboard-header__actions-row">
          <button type="button" className="button secondary" onClick={handleCreateExport}>
            Create CSV Export
          </button>
          {job?.download_url ? (
            <a className="button tertiary" href={job.download_url}>
              Download Latest Export
            </a>
          ) : null}
        </div>
        {job ? (
          <p className="dashboard-field__label" style={{ marginTop: '0.75rem' }}>
            Job {job.id}: {job.status}
          </p>
        ) : null}
      </div>

      <div className="panel">
        <h2>Saved Views</h2>
        <div className="dashboard-header__controls" style={{ marginBottom: '0.75rem' }}>
          <label className="dashboard-field">
            <span className="dashboard-field__label">Name</span>
            <input
              value={viewName}
              onChange={(event) => setViewName(event.target.value)}
              placeholder="Weekly executive filter set"
            />
          </label>
          <button type="button" className="button secondary" onClick={handleCreateSavedView}>
            Save View
          </button>
        </div>

        {status === 'loading' ? <p>Loading saved views...</p> : null}
        {savedViews.length === 0 && status === 'idle' ? <p>No saved views yet.</p> : null}

        {savedViews.length > 0 ? (
          <div className="table-responsive">
            <table className="dashboard-table">
              <thead>
                <tr className="dashboard-table__header-row">
                  <th className="dashboard-table__header-cell">Name</th>
                  <th className="dashboard-table__header-cell">Description</th>
                  <th className="dashboard-table__header-cell">Shared</th>
                  <th className="dashboard-table__header-cell">Updated</th>
                </tr>
              </thead>
              <tbody>
                {savedViews.map((view) => (
                  <tr key={view.id} className="dashboard-table__row dashboard-table__row--zebra">
                    <td className="dashboard-table__cell">{view.name}</td>
                    <td className="dashboard-table__cell">{view.description || '—'}</td>
                    <td className="dashboard-table__cell">{view.is_shared ? 'Yes' : 'No'}</td>
                    <td className="dashboard-table__cell">{view.updated_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </section>
  );
};

export default GoogleAdsReportsPage;
