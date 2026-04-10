import { useCallback, useEffect, useMemo, useState } from 'react';

import { fetchGoogleAdsList, type GoogleAdsListResponse } from '../../lib/googleAdsDashboard';
import { appendQueryParams } from '../../lib/apiClient';
import DashboardState from '../DashboardState';

type Row = Record<string, unknown>;

type Props = {
  eyebrow: string;
  title: string;
  description?: string;
  endpoint: string;
  query?: Record<string, string | number | boolean>;
  emptyMessage?: string;
};

const GoogleAdsDataTablePage = ({
  eyebrow,
  title,
  description,
  endpoint,
  query,
  emptyMessage = 'No data available for this range.',
}: Props) => {
  const [payload, setPayload] = useState<GoogleAdsListResponse<Row>>({ count: 0, results: [] });
  const [status, setStatus] = useState<'idle' | 'loading' | 'error'>('idle');
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    setStatus('loading');
    setError(null);
    try {
      const path = query ? appendQueryParams(endpoint, query) : endpoint;
      const response = await fetchGoogleAdsList<Row>(path);
      if (signal?.aborted) {
        return;
      }
      setPayload(response);
      setStatus('idle');
    } catch (err) {
      if (signal?.aborted) {
        return;
      }
      const message = err instanceof Error ? err.message : 'Failed to load Google Ads data.';
      setError(message);
      setStatus('error');
    }
  }, [endpoint, query]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => {
      controller.abort();
    };
  }, [load]);

  const columns = useMemo(() => {
    const sample = payload.results[0];
    if (!sample) {
      return [] as string[];
    }
    return Object.keys(sample);
  }, [payload.results]);

  return (
    <section className="dashboardPage">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">{eyebrow}</p>
        <h1 className="dashboardHeading">{title}</h1>
        {description ? <p className="dashboardSubtitle">{description}</p> : null}
      </header>

      {status === 'loading' ? (
        <DashboardState variant="loading" layout="page" message="Loading Google Ads data..." />
      ) : null}
      {status === 'error' ? (
        <DashboardState
          variant="error"
          layout="page"
          title={`${title} unavailable`}
          message={error ?? 'Failed to load Google Ads data.'}
          actionLabel="Retry"
          onAction={() => void load()}
        />
      ) : null}

      {status !== 'loading' && payload.results.length === 0 ? (
        <div className="panel">
          <p>{emptyMessage}</p>
        </div>
      ) : null}

      {payload.results.length > 0 ? (
        <div className="panel">
          <h2>
            Results ({payload.count})
            {payload.source_engine ? (
              <span className="dashboard-field__label" style={{ marginLeft: '0.75rem' }}>
                Source: {payload.source_engine}
              </span>
            ) : null}
          </h2>
          <div className="table-responsive">
            <table className="dashboard-table">
              <thead>
                <tr className="dashboard-table__header-row">
                  {columns.map((column) => (
                    <th key={column} className="dashboard-table__header-cell">
                      {column.replace(/_/g, ' ')}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {payload.results.map((row, rowIndex) => (
                  <tr
                    key={`${rowIndex}-${String(row.id ?? row.campaign_id ?? row.ad_id ?? row.customer_id ?? '')}`}
                    className="dashboard-table__row dashboard-table__row--zebra"
                  >
                    {columns.map((column) => (
                      <td key={column} className="dashboard-table__cell">
                        {String(row[column] ?? '—')}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </section>
  );
};

export default GoogleAdsDataTablePage;
