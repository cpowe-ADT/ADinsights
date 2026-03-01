import type { MetaExportJob } from '../../lib/metaPageInsights';

type MetaPageExportHistoryProps = {
  title?: string;
  jobs: MetaExportJob[];
  error?: string | null;
  isLoading?: boolean;
  onRefresh: () => void;
  onDownload: (jobId: string) => void;
};

const MetaPageExportHistory = ({
  title = 'Export history',
  jobs,
  error,
  isLoading = false,
  onRefresh,
  onDownload,
}: MetaPageExportHistoryProps) => {
  return (
    <article className="panel" style={{ marginTop: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', alignItems: 'baseline' }}>
        <h3 style={{ margin: 0 }}>{title}</h3>
        <button type="button" className="button tertiary" onClick={onRefresh} disabled={isLoading}>
          Refresh
        </button>
      </div>
      {error ? (
        <p role="alert" style={{ marginTop: '0.5rem' }}>
          {error}
        </p>
      ) : null}
      {jobs.length === 0 ? <p className="muted">No exports yet.</p> : null}
      {jobs.length > 0 ? (
        <div className="table-responsive" style={{ marginTop: '0.75rem' }}>
          <table className="dashboard-table">
            <thead>
              <tr className="dashboard-table__header-row">
                <th className="dashboard-table__header-cell">Created</th>
                <th className="dashboard-table__header-cell">Format</th>
                <th className="dashboard-table__header-cell">Status</th>
                <th className="dashboard-table__header-cell">Action</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id} className="dashboard-table__row dashboard-table__row--zebra">
                  <td className="dashboard-table__cell">{job.created_at?.slice(0, 19) ?? '—'}</td>
                  <td className="dashboard-table__cell">{job.export_format}</td>
                  <td className="dashboard-table__cell">{job.status}</td>
                  <td className="dashboard-table__cell">
                    <button
                      type="button"
                      className="button tertiary"
                      disabled={job.status !== 'completed'}
                      onClick={() => onDownload(job.id)}
                    >
                      Download
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </article>
  );
};

export default MetaPageExportHistory;

