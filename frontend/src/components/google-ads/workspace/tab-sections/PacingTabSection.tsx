import { useMemo } from 'react';

import {
  DistributionBar,
  EmptyState,
  GaugeRing,
  KpiTile,
  derivePacingVariant,
} from '../../../viz';
import {
  countOverPacingCampaigns,
  derivePacingPct,
  rollupPacingKpis,
  type GoogleAdsPacingCampaignRow,
  type GoogleAdsPacingPayload,
} from '../../../../lib/googleAdsAggregates';
import { formatCurrency } from '../../../../lib/formatNumber';

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
 *   2. KpiTile × 4 — Spend MTD, Budget Month, Forecast Month End, and
 *      "Over-pacing campaigns" (count where per-campaign pace_pct > 1.0).
 *      The last tile is suppressed when the pacing payload has no
 *      campaigns array.
 *   3. Per-campaign pacing bars (GA-A1) — DistributionBar of pace_pct
 *      sorted descending; only campaigns with a matched budget are shown.
 *      Rows without a budget (pace_pct === null) render separately in the
 *      summary table as "—".
 *   4. Summary table (single row) replacing the legacy 7-row key/val `<dl>`.
 */
const PacingTabSection = ({ data, status, error }: Props) => {
  const pacing = useMemo(() => {
    if (!data || typeof data !== 'object' || Array.isArray(data)) return null;
    return data as GoogleAdsPacingPayload;
  }, [data]);

  const kpis = useMemo(() => rollupPacingKpis(pacing), [pacing]);
  const pacingPct = useMemo(() => derivePacingPct(pacing), [pacing]);
  const campaigns: GoogleAdsPacingCampaignRow[] = useMemo(
    () => (pacing && Array.isArray(pacing.campaigns) ? pacing.campaigns : []),
    [pacing],
  );
  const overPacingCount = useMemo(() => countOverPacingCampaigns(pacing), [pacing]);
  const hasCampaignsPayload = pacing != null && Array.isArray(pacing.campaigns);

  const distributionData = useMemo(() => {
    // Only include campaigns that have a computable pace_pct; those lacking
    // a matched budget cannot be meaningfully positioned on the bar scale.
    return campaigns
      .filter((row) => row.pace_pct !== null && row.pace_pct !== undefined)
      .map((row) => ({
        label: String(row.campaign_name ?? row.campaign_id ?? 'Unknown'),
        value: Number(row.pace_pct ?? 0),
      }))
      .sort((a, b) => b.value - a.value);
  }, [campaigns]);

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
          {hasCampaignsPayload ? (
            <KpiTile
              label="Over-pacing campaigns"
              value={overPacingCount}
              format="number"
            />
          ) : null}
        </div>
      </section>

      {campaigns.length > 0 ? (
        <section className="panel" data-testid="google-ads-pacing-campaigns">
          <h2>Per-campaign pacing</h2>
          {distributionData.length > 0 ? (
            <DistributionBar
              data={distributionData}
              yFormat="percent"
              ariaLabel="Google Ads per-campaign pacing as a share of monthly budget"
              emptyReasonCode="no_pacing_data"
            />
          ) : null}
          <div className="table-responsive" style={{ marginTop: '0.75rem' }}>
            <table className="dashboard-table">
              <thead>
                <tr className="dashboard-table__header-row">
                  <th className="dashboard-table__header-cell">Campaign</th>
                  <th className="dashboard-table__header-cell">Spend MTD</th>
                  <th className="dashboard-table__header-cell">Budget</th>
                  <th className="dashboard-table__header-cell">Pace %</th>
                  <th className="dashboard-table__header-cell">Variance</th>
                </tr>
              </thead>
              <tbody>
                {campaigns.map((row, idx) => {
                  const hasBudget =
                    row.budget_amount !== null && row.budget_amount !== undefined;
                  const pacePct = row.pace_pct;
                  const variance = row.variance;
                  const key = `${String(row.campaign_id ?? row.campaign_name ?? idx)}-${idx}`;
                  return (
                    <tr
                      key={key}
                      className="dashboard-table__row dashboard-table__row--zebra"
                    >
                      <td className="dashboard-table__cell">
                        {String(row.campaign_name ?? row.campaign_id ?? '—')}
                      </td>
                      <td className="dashboard-table__cell">
                        {formatCurrency(Number(row.spend_mtd ?? 0), 'JMD')}
                      </td>
                      <td className="dashboard-table__cell">
                        {hasBudget
                          ? formatCurrency(Number(row.budget_amount ?? 0), 'JMD')
                          : '—'}
                      </td>
                      <td className="dashboard-table__cell">
                        {pacePct === null || pacePct === undefined
                          ? '—'
                          : `${(Number(pacePct) * 100).toFixed(0)}%`}
                      </td>
                      <td className="dashboard-table__cell">
                        {variance === null || variance === undefined
                          ? '—'
                          : formatCurrency(Number(variance), 'JMD')}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

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
