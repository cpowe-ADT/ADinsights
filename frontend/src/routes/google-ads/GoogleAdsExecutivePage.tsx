import { useEffect, useState } from 'react';

import { fetchGoogleAdsExecutive, type GoogleAdsExecutiveResponse } from '../../lib/googleAdsDashboard';

const metricLabels: Record<string, string> = {
  spend: 'Spend',
  impressions: 'Impressions',
  clicks: 'Clicks',
  ctr: 'CTR',
  avg_cpc: 'Avg CPC',
  conversions: 'Conversions',
  conversion_rate: 'Conv Rate',
  cpa: 'CPA',
  conversion_value: 'Conv Value',
  roas: 'ROAS',
};

const GoogleAdsExecutivePage = () => {
  const [data, setData] = useState<GoogleAdsExecutiveResponse | null>(null);
  const [status, setStatus] = useState<'idle' | 'loading' | 'error'>('loading');
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    const load = async () => {
      setStatus('loading');
      setError('');
      try {
        const response = await fetchGoogleAdsExecutive();
        if (!active) {
          return;
        }
        setData(response);
        setStatus('idle');
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : 'Failed to load executive dashboard.');
        setStatus('error');
      }
    };

    void load();
    return () => {
      active = false;
    };
  }, []);

  return (
    <section className="dashboardPage">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Google Ads</p>
        <h1 className="dashboardHeading">Executive Overview</h1>
        <p className="dashboardSubtitle">
          Spend, performance, pacing, and top movers across your scoped Google Ads accounts.
        </p>
      </header>

      {status === 'loading' ? <div className="dashboard-state dashboard-state--page">Loading overview...</div> : null}
      {status === 'error' ? (
        <div className="dashboard-state dashboard-state--page" role="alert">
          {error}
        </div>
      ) : null}

      {data ? (
        <>
          <div className="panel" style={{ marginBottom: '1rem' }}>
            <h2>
              KPI Summary
              <span className="dashboard-field__label" style={{ marginLeft: '0.75rem' }}>
                Source: {data.source_engine}
              </span>
            </h2>
            <div className="kpi-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.75rem' }}>
              {Object.entries(data.metrics).map(([key, value]) => (
                <article key={key} className="metric-card metric-card--compact">
                  <p className="metric-card__label">{metricLabels[key] ?? key}</p>
                  <p className="metric-card__value">{Number.isFinite(value) ? value.toFixed(2) : String(value)}</p>
                </article>
              ))}
            </div>
          </div>

          <div className="panel" style={{ marginBottom: '1rem' }}>
            <h2>Pacing</h2>
            <div className="table-responsive">
              <table className="dashboard-table">
                <tbody>
                  {Object.entries(data.pacing).map(([key, value]) => (
                    <tr key={key} className="dashboard-table__row dashboard-table__row--zebra">
                      <td className="dashboard-table__cell">{key.replace(/_/g, ' ')}</td>
                      <td className="dashboard-table__cell">{value == null ? '—' : Number(value).toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="panel" style={{ marginBottom: '1rem' }}>
            <h2>Top Movers</h2>
            <div className="table-responsive">
              <table className="dashboard-table">
                <thead>
                  <tr className="dashboard-table__header-row">
                    <th className="dashboard-table__header-cell">Campaign</th>
                    <th className="dashboard-table__header-cell">Spend</th>
                    <th className="dashboard-table__header-cell">Conversion Value</th>
                    <th className="dashboard-table__header-cell">ROAS</th>
                  </tr>
                </thead>
                <tbody>
                  {data.movers.map((row) => (
                    <tr key={String(row.campaign_id)} className="dashboard-table__row dashboard-table__row--zebra">
                      <td className="dashboard-table__cell">{String(row.campaign_name ?? row.campaign_id)}</td>
                      <td className="dashboard-table__cell">{Number(row.spend ?? 0).toFixed(2)}</td>
                      <td className="dashboard-table__cell">{Number(row.conversion_value ?? 0).toFixed(2)}</td>
                      <td className="dashboard-table__cell">{Number(row.roas ?? 0).toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="panel">
            <h2>Trend</h2>
            <div className="table-responsive">
              <table className="dashboard-table">
                <thead>
                  <tr className="dashboard-table__header-row">
                    <th className="dashboard-table__header-cell">Date</th>
                    <th className="dashboard-table__header-cell">Spend</th>
                    <th className="dashboard-table__header-cell">Conversions</th>
                    <th className="dashboard-table__header-cell">ROAS</th>
                  </tr>
                </thead>
                <tbody>
                  {data.trend.map((point) => (
                    <tr key={String(point.date)} className="dashboard-table__row dashboard-table__row--zebra">
                      <td className="dashboard-table__cell">{String(point.date)}</td>
                      <td className="dashboard-table__cell">{Number(point.spend ?? 0).toFixed(2)}</td>
                      <td className="dashboard-table__cell">{Number(point.conversions ?? 0).toFixed(2)}</td>
                      <td className="dashboard-table__cell">{Number(point.roas ?? 0).toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
};

export default GoogleAdsExecutivePage;
