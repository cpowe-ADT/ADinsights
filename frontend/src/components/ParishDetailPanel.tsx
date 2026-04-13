import type { DemographicsData, ParishAggregate } from '../state/useDashboardStore';
import { formatCurrency, formatNumber, formatPercent, formatRatio } from '../lib/format';
import DashboardState from './DashboardState';
import AgeDistributionBar from './AgeDistributionBar';

interface ParishDetailPanelProps {
  parish: ParishAggregate | undefined;
  currency: string;
  demographics?: DemographicsData;
  onClear: () => void;
}

const ParishDetailPanel = ({ parish, currency, demographics, onClear }: ParishDetailPanelProps) => {
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

  const campaigns = parish.campaigns ?? [];
  const hasDemographics = demographics && demographics.byAgeGender.length > 0;

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

      {campaigns.length > 0 && (
        <div className="parishCampaignList">
          <h4 className="parishSubheading">Active campaigns</h4>
          <ul className="parishCampaignItems">
            {campaigns.map((c) => (
              <li key={c.id} className="parishCampaignItem">
                <span className="parishCampaignName" title={c.name}>{c.name}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {hasDemographics && (
        <div className="parishDemographicsMini">
          <h4 className="parishSubheading">Audience snapshot</h4>
          <AgeDistributionBar
            data={demographics.byAgeGender}
            metric="impressions"
            currency={cur}
          />
        </div>
      )}

      <div className="parishDetailActions">
        <button type="button" className="button tertiary" onClick={onClear}>
          Clear selection
        </button>
      </div>
    </div>
  );
};

export default ParishDetailPanel;
