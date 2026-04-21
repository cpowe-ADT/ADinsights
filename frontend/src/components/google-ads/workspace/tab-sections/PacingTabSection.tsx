import { useMemo } from 'react';

import {
  EmptyState,
  GaugeRing,
  KpiTile,
  derivePacingVariant,
} from '../../../viz';
import {
  derivePacingPct,
  rollupPacingKpis,
  type GoogleAdsPacingPayload,
} from '../../../../lib/googleAdsAggregates';

type Props = {
  data: unknown;
  status: 'idle' | 'loading' | 'success' | 'error';
  error: string;
};

const EmptyIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="40"
    height="40"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    aria-hidden="true"
  >
    <circle cx="12" cy="12" r="10" />
    <path d="M12 6v6l4 2" />
  </svg>
);

/**
 * Sprint 3 — Pacing tab. Architect §6.7.
 *
 * Layout:
 *   1. GaugeRing — value = `pacing_pct` (derived via spend_mtd/budget_month
 *      fallback per §4 audit); variant via kit `derivePacingVariant`.
 *   2. KpiTile × 3 — Spend MTD, Budget Month, Forecast Month End.
 *   3. Summary table (single row) replacing the legacy 7-row key/val `<dl>`.
 *
 * Variance bar is deferred (§4 — per-campaign budget rows are not in the
 * backend payload today). [NEW-ENDPOINT] required for that.
 */
const PacingTabSection = ({ data, status, error }: Props) => {
  const pacing = useMemo(() => {
    if (!data || typeof data !== 'object' || Array.isArray(data)) return null;
    return data as GoogleAdsPacingPayload;
  }, [data]);

  const kpis = useMemo(() => rollupPacingKpis(pacing), [pacing]);
  const pacingPct = useMemo(() => derivePacingPct(pacing), [pacing]);

  if (status === 'loading' && !pacing) {
    return <div className="panel">Loading pacing...</div>;
  }
  if (status === 'error' && !pacing) {
    return (
      <div className="panel" role="alert">
        {error}
      </div>
    );
  }

  // Both values zero/null → no pacing data at all.
  const noPacingData = !pacing || (kpis.spendMtd === 0 && kpis.budgetMonth === 0);
  if (noPacingData) {
    return (
      <EmptyState
        icon={<EmptyIcon />}
        title="No pacing data"
        message="Select a Google Ads account with an active monthly budget to see pacing."
        reasonCode="no_pacing_data"
      />
    );
  }

  const variant = pacingPct !== null ? derivePacingVariant(pacingPct) : undefined;

  return (
    <div className="gads-workspace__tab-grid" data-testid="google-ads-pacing-section">
      <section className="panel">
        <h2>Pacing</h2>
        <GaugeRing
          value={pacingPct ?? Number.NaN}
          max={1.2}
          label="Spend vs budget"
          variant={variant}
          ariaLabel={
            pacingPct !== null
              ? `Pacing ${(pacingPct * 100).toFixed(0)} percent of monthly budget`
              : 'Pacing data unavailable'
          }
          emptyReasonCode="no_pacing_data"
        />
      </section>

      <section className="panel">
        <h2>Budget KPIs</h2>
        <div
          className="gads-workspace__kpi-grid"
          role="list"
          aria-label="Google Ads pacing KPIs"
        >
          <KpiTile
            label="Spend MTD"
            value={kpis.spendMtd}
            format="currency"
            currency="JMD"
          />
          <KpiTile
            label="Budget Month"
            value={kpis.budgetMonth}
            format="currency"
            currency="JMD"
          />
          <KpiTile
            label="Forecast Month End"
            value={kpis.forecast}
            format="currency"
            currency="JMD"
          />
        </div>
        {/* Variance bar intentionally deferred — architect §4 + §6.7:
            per-campaign budget rows are not available from /budgets/pacing/. */}
      </section>

      <section className="panel">
        <h2>{pacing?.month ?? 'Pacing summary'}</h2>
        <div className="table-responsive">
          <table className="dashboard-table">
            <thead>
              <tr className="dashboard-table__header-row">
                <th className="dashboard-table__header-cell">Metric</th>
                <th className="dashboard-table__header-cell">Value</th>
              </tr>
            </thead>
            <tbody>
              <tr className="dashboard-table__row dashboard-table__row--zebra">
                <td className="dashboard-table__cell">Over/Under</td>
                <td className="dashboard-table__cell">{kpis.overUnder.toFixed(2)}</td>
              </tr>
              <tr className="dashboard-table__row dashboard-table__row--zebra">
                <td className="dashboard-table__cell">Runway days</td>
                <td className="dashboard-table__cell">
                  {pacing?.runway_days == null ? '—' : Number(pacing.runway_days).toFixed(1)}
                </td>
              </tr>
              <tr className="dashboard-table__row dashboard-table__row--zebra">
                <td className="dashboard-table__cell">Overspend risk</td>
                <td className="dashboard-table__cell">
                  {pacing?.alerts?.overspend_risk ? 'Yes' : 'No'}
                </td>
              </tr>
              <tr className="dashboard-table__row dashboard-table__row--zebra">
                <td className="dashboard-table__cell">Underdelivery</td>
                <td className="dashboard-table__cell">
                  {pacing?.alerts?.underdelivery ? 'Yes' : 'No'}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
};

export default PacingTabSection;
