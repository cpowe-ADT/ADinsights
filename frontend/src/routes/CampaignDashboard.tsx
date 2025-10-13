import CampaignTable from "../components/CampaignTable";
import CampaignTrendChart from "../components/CampaignTrendChart";
import ChartCard from "../components/ChartCard";
import FullPageLoader from "../components/FullPageLoader";
import KpiCard from "../components/KpiCard";
import ParishMap from "../components/ParishMap";
import useDashboardStore from "../state/useDashboardStore";
import { formatCurrency, formatNumber, formatRatio } from "../lib/format";

const CampaignDashboard = () => {
  const { campaign, campaignRows } = useDashboardStore((state) => ({
    campaign: state.campaign,
    campaignRows: state.getCampaignRowsForSelectedParish(),
  }));

  if (campaign.status === "loading" && !campaign.data) {
    return <FullPageLoader message="Loading campaign performance…" />;
  }

  if (campaign.status === "error" && !campaign.data) {
    return <div className="status-message error">{campaign.error ?? "Unable to load campaign performance."}</div>;
  }

  if (!campaign.data) {
    return <div className="status-message muted">Campaign performance will appear once metrics are ingested.</div>;
  }

  const { summary, trend } = campaign.data;
  const currency = summary.currency ?? "USD";

  const kpis = [
    { label: "Spend", value: formatCurrency(summary.totalSpend, currency) },
    { label: "Impressions", value: formatNumber(summary.totalImpressions) },
    { label: "Clicks", value: formatNumber(summary.totalClicks) },
    { label: "Conversions", value: formatNumber(summary.totalConversions) },
    { label: "Avg. ROAS", value: formatRatio(summary.averageRoas, 2) },
  ];

  const hasTrendData = trend.length > 0;
  const dateRangeFormatter = new Intl.DateTimeFormat("en-JM", { month: "short", day: "numeric" });
  const chartFooter = hasTrendData
    ? (
        <div className="chart-card__footer-grid">
          <div>
            <span className="chart-card__footer-label">Peak daily spend</span>
            <strong>{formatCurrency(Math.max(...trend.map((point) => point.spend)), currency)}</strong>
          </div>
          <div className="chart-card__footer-dates">
            <span>{dateRangeFormatter.format(new Date(trend[0].date))}</span>
            <span aria-hidden="true">–</span>
            <span>{dateRangeFormatter.format(new Date(trend[trend.length - 1].date))}</span>
          </div>
        </div>
      )
    : undefined;

  return (
    <div className="dashboard-grid">
      <section className="kpi-grid" aria-label="Campaign KPIs">
        {kpis.map((kpi) => (
          <KpiCard key={kpi.label} label={kpi.label} value={kpi.value} />
        ))}
      </section>
      <ChartCard title="Daily spend trend" footer={chartFooter}>
        <CampaignTrendChart data={trend} currency={currency} />
      </ChartCard>
      <section className="panel map-panel">
        <header className="panel-header">
          <h2>Parish heatmap</h2>
          <p className="muted">Click a parish to filter the performance tables below.</p>
        </header>
        <ParishMap />
      </section>
      <section className="panel full-width">
        <CampaignTable rows={campaignRows} currency={currency} />
      </section>
    </div>
  );
};

export default CampaignDashboard;
