import type { SummaryRecord } from '../types';

type Props = {
  summary: SummaryRecord | null;
};

const OverviewTabSection = ({ summary }: Props) => {
  if (!summary) {
    return <div className="panel">Loading overview...</div>;
  }

  return (
    <div className="gads-workspace__tab-grid">
      <section className="panel">
        <h2>Spend / Conversions / ROAS trend</h2>
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
              {summary.trend.map((point) => (
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
      </section>

      <section className="panel">
        <h2>Top movers</h2>
        <div className="table-responsive">
          <table className="dashboard-table">
            <thead>
              <tr className="dashboard-table__header-row">
                <th className="dashboard-table__header-cell">Campaign</th>
                <th className="dashboard-table__header-cell">Spend</th>
                <th className="dashboard-table__header-cell">Conv value</th>
                <th className="dashboard-table__header-cell">ROAS</th>
              </tr>
            </thead>
            <tbody>
              {summary.movers.map((row) => (
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
      </section>

      <section className="panel">
        <h2>Pacing forecast</h2>
        <dl className="gads-workspace__keyvals">
          <dt>Spend MTD</dt>
          <dd>{Number(summary.pacing.spend_mtd ?? 0).toFixed(2)}</dd>
          <dt>Budget month</dt>
          <dd>{Number(summary.pacing.budget_month ?? 0).toFixed(2)}</dd>
          <dt>Forecast month-end</dt>
          <dd>{Number(summary.pacing.forecast_month_end ?? 0).toFixed(2)}</dd>
          <dt>Over/Under</dt>
          <dd>{Number(summary.pacing.over_under ?? 0).toFixed(2)}</dd>
          <dt>Pacing %</dt>
          <dd>{Number(summary.pacing.pacing_pct ?? 0).toFixed(2)}</dd>
        </dl>
      </section>
    </div>
  );
};

export default OverviewTabSection;
