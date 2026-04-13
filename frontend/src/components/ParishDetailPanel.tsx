import type { ParishAggregate } from '../state/useDashboardStore';
import { formatCurrency, formatNumber, formatPercent, formatRatio } from '../lib/format';
import DashboardState from './DashboardState';

interface ParishDetailPanelProps {
  parish: ParishAggregate | undefined;
  currency: string;
  onClear: () => void;
}

const ParishDetailPanel = ({ parish, currency, onClear }: ParishDetailPanelProps) => {
  if (!parish) {
    return (
      <DashboardState
        variant="empty"
        title="No parish selected"
        message="Click a parish on the map or a row in the table to see its detailed metrics."
        layout="compact"
      />
    );
  }

  const cur = parish.currency ?? currency;
  const metrics = [
    { label: 'Spend', value: formatCurrency(parish.spend, cur) },
    { label: 'Impressions', value: formatNumber(parish.impressions) },
    { label: 'Clicks', value: formatNumber(parish.clicks) },
    { label: 'Conversions', value: formatNumber(parish.conversions) },
    { label: 'CTR', value: formatPercent(parish.ctr ?? 0, 2) },
    { label: 'CPC', value: formatCurrency(parish.cpc ?? 0, cur) },
    { label: 'CPM', value: formatCurrency(parish.cpm ?? 0, cur) },
    { label: 'ROAS', value: formatRatio(parish.roas ?? 0, 2) },
    { label: 'Campaigns', value: formatNumber(parish.campaignCount ?? 0) },
  ];

  return (
    <div className="parishDetailContent">
      <h3 className="parishDetailHeading">{parish.parish}</h3>
      <ul className="parishDetailList">
        {metrics.map((m) => (
          <li key={m.label}>
            <span className="detailLabel">{m.label}</span>
            <span className="detailValue">{m.value}</span>
          </li>
        ))}
      </ul>
      <div className="parishDetailActions">
        <button type="button" className="button tertiary" onClick={onClear}>
          Clear selection
        </button>
      </div>
    </div>
  );
};

export default ParishDetailPanel;
