import { useEffect, useMemo, useState } from 'react';

import { EmptyState, KpiTile, TrendLine } from '../../components/viz';
import {
  deriveTrendSeries,
  rollupOverviewKpis,
} from '../../lib/googleAdsAggregates';
import {
  fetchGoogleAdsExecutive,
  type GoogleAdsExecutiveResponse,
} from '../../lib/googleAdsDashboard';
import { resolveFilterRange } from '../../lib/dashboardFilters';
import useDashboardStore from '../../state/useDashboardStore';

const EmptyIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
    <circle cx="12" cy="12" r="10" />
    <path d="M8 12h8" />
  </svg>
);

/**
 * Sprint 3 — Executive Overview (legacy mode). Replaces the raw-table
 * layout with the shared viz kit. IS% is intentionally absent per
 * architect §4 (not in the backend payload).
 */
const GoogleAdsExecutivePage = () => {
  const [data, setData] = useState<GoogleAdsExecutiveResponse | null>(null);
  const [status, setStatus] = useState<'idle' | 'loading' | 'error'>('loading');
  const [error, setError] = useState('');

  // NB1 fix: subscribe to filters so stale data is not shown after FilterBar changes.
  const filters = useDashboardStore((state) => state.filters);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setStatus('loading');
      setError('');
      try {
        const { start, end } = resolveFilterRange(filters);
        const response = await fetchGoogleAdsExecutive({
          platforms: 'google_ads',
          customer_id: filters.accountId || undefined,
          start_date: start || undefined,
          end_date: end || undefined,
        });
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
  }, [filters]);

  const kpis = useMemo(() => rollupOverviewKpis(data), [data]);
  const trendPoints = useMemo(() => deriveTrendSeries(data?.trend), [data?.trend]);

  return (
    <section className="dashboardPage">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Google Ads</p>
        <h1 className="dashboardHeading">Executive Overview</h1>
        <p className="dashboardSubtitle">
          Spend, performance, pacing, and top movers across your scoped Google Ads accounts.
        </p>
      </header>

      {status === 'loading' ? (
        <div className="dashboard-state dashboard-state--page">Loading overview...</div>
      ) : null}
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
            <div
              className="gads-workspace__kpi-grid"
              role="list"
              aria-label="Google Ads executive KPIs"
            >
              <KpiTile label="Cost" value={kpis.spend} format="currency" currency="JMD" />
              <KpiTile label="Conversions" value={kpis.conversions} format="number" />
              <KpiTile label="CPA" value={kpis.cpa} format="currency" currency="JMD" />
              <KpiTile label="ROAS" value={kpis.roas} format="number" />
            </div>
          </div>

          <div className="panel" style={{ marginBottom: '1rem' }}>
            <h2>Trend</h2>
            {trendPoints.length === 0 ? (
              <EmptyState
                icon={<EmptyIcon />}
                title="No trend data for this range"
                message="Adjust the date range or account filter to see a daily trend."
                reasonCode="no_data_for_range"
              />
            ) : (
              <TrendLine
                data={trendPoints}
                series={[
                  { key: 'spend', label: 'Cost', yAxis: 'left' },
                  { key: 'conversions', label: 'Conversions', yAxis: 'right' },
                ]}
                yFormat="currency"
                rightYFormat="number"
                ariaLabel="Google Ads executive daily cost and conversions"
                emptyReasonCode="no_data_for_range"
              />
            )}
          </div>

          <div className="panel" style={{ marginBottom: '1rem' }}>
            <h2>Pacing</h2>
            <div className="table-responsive">
              <table className="dashboard-table">
                <tbody>
                  {Object.entries(data.pacing).map(([key, value]) => (
                    <tr key={key} className="dashboard-table__row dashboard-table__row--zebra">
                      <td className="dashboard-table__cell">{key.replace(/_/g, ' ')}</td>
                      <td className="dashboard-table__cell">
                        {value == null ? '—' : Number(value).toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="panel">
            <h2>Top Movers</h2>
            <div className="table-responsive">
              <table className="dashboard-table">
                <thead>
                  <tr className="dashboard-table__header-row">
                    <th className="dashboard-table__header-cell">Campaign</th>
                    <th className="dashboard-table__header-cell">Cost</th>
                    <th className="dashboard-table__header-cell">Conversion Value</th>
                    <th className="dashboard-table__header-cell">ROAS</th>
                  </tr>
                </thead>
                <tbody>
                  {data.movers.map((row) => (
                    <tr
                      key={String(row.campaign_id)}
                      className="dashboard-table__row dashboard-table__row--zebra"
                    >
                      <td className="dashboard-table__cell">
                        {String(row.campaign_name ?? row.campaign_id)}
                      </td>
                      <td className="dashboard-table__cell">{Number(row.spend ?? 0).toFixed(2)}</td>
                      <td className="dashboard-table__cell">
                        {Number(row.conversion_value ?? 0).toFixed(2)}
                      </td>
                      <td className="dashboard-table__cell">{Number(row.roas ?? 0).toFixed(2)}</td>
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
