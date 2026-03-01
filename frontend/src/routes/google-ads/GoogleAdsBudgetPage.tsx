import { useEffect, useState } from 'react';

import { get } from '../../lib/apiClient';

type BudgetPacingPayload = {
  month: string;
  spend_mtd: number;
  budget_month: number;
  forecast_month_end: number;
  over_under: number;
  runway_days: number | null;
  alerts: {
    overspend_risk: boolean;
    underdelivery: boolean;
  };
};

const GoogleAdsBudgetPage = () => {
  const [data, setData] = useState<BudgetPacingPayload | null>(null);
  const [status, setStatus] = useState<'idle' | 'loading' | 'error'>('loading');
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    const load = async () => {
      setStatus('loading');
      setError('');
      try {
        const response = await get<BudgetPacingPayload>('/analytics/google-ads/budgets/pacing/');
        if (!active) {
          return;
        }
        setData(response);
        setStatus('idle');
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : 'Failed to load budget pacing.');
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
        <h1 className="dashboardHeading">Budget & Pacing</h1>
        <p className="dashboardSubtitle">Spend pacing, forecast, and delivery risk guardrails.</p>
      </header>

      {status === 'loading' ? <div className="dashboard-state dashboard-state--page">Loading pacing...</div> : null}
      {status === 'error' ? (
        <div className="dashboard-state dashboard-state--page" role="alert">
          {error}
        </div>
      ) : null}

      {data ? (
        <div className="panel">
          <h2>{data.month}</h2>
          <div className="table-responsive">
            <table className="dashboard-table">
              <tbody>
                <tr className="dashboard-table__row dashboard-table__row--zebra">
                  <td className="dashboard-table__cell">Spend MTD</td>
                  <td className="dashboard-table__cell">{data.spend_mtd.toFixed(2)}</td>
                </tr>
                <tr className="dashboard-table__row dashboard-table__row--zebra">
                  <td className="dashboard-table__cell">Budget Month</td>
                  <td className="dashboard-table__cell">{data.budget_month.toFixed(2)}</td>
                </tr>
                <tr className="dashboard-table__row dashboard-table__row--zebra">
                  <td className="dashboard-table__cell">Forecast Month End</td>
                  <td className="dashboard-table__cell">{data.forecast_month_end.toFixed(2)}</td>
                </tr>
                <tr className="dashboard-table__row dashboard-table__row--zebra">
                  <td className="dashboard-table__cell">Over/Under</td>
                  <td className="dashboard-table__cell">{data.over_under.toFixed(2)}</td>
                </tr>
                <tr className="dashboard-table__row dashboard-table__row--zebra">
                  <td className="dashboard-table__cell">Runway Days</td>
                  <td className="dashboard-table__cell">{data.runway_days == null ? '—' : data.runway_days.toFixed(1)}</td>
                </tr>
                <tr className="dashboard-table__row dashboard-table__row--zebra">
                  <td className="dashboard-table__cell">Overspend Risk</td>
                  <td className="dashboard-table__cell">{data.alerts.overspend_risk ? 'Yes' : 'No'}</td>
                </tr>
                <tr className="dashboard-table__row dashboard-table__row--zebra">
                  <td className="dashboard-table__cell">Underdelivery</td>
                  <td className="dashboard-table__cell">{data.alerts.underdelivery ? 'Yes' : 'No'}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </section>
  );
};

export default GoogleAdsBudgetPage;
