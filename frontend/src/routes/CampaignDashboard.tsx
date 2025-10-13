import CampaignTable from "../components/CampaignTable";
import CampaignTrendChart from "../components/CampaignTrendChart";
import FullPageLoader from "../components/FullPageLoader";
import KpiCard from "../components/KpiCard";
import ParishMap from "../components/ParishMap";
import useDashboardStore from "../state/useDashboardStore";
import { formatCurrency, formatNumber, formatRatio } from "../lib/format";

const CampaignDashboard = () => {
  const { campaign } = useDashboardStore((state) => ({ campaign: state.campaign }));

  if (campaign.status === "loading" && !campaign.data) {
    return <FullPageLoader message="Loading campaign performance…" />;
  }

  if (campaign.status === "error" && !campaign.data) {
    return <div className="status-message error">{campaign.error ?? "Unable to load campaign performance."}</div>;
  }

  if (!campaign.data) {
    return <div className="status-message muted">Campaign performance will appear once metrics are ingested.</div>;
  }

  const { summary, trend, rows } = campaign.data;
  const currency = summary.currency ?? "USD";

  const kpis = [
    { label: "Spend", value: formatCurrency(summary.totalSpend, currency) },
    { label: "Impressions", value: formatNumber(summary.totalImpressions) },
    { label: "Clicks", value: formatNumber(summary.totalClicks) },
    { label: "Conversions", value: formatNumber(summary.totalConversions) },
    { label: "Avg. ROAS", value: formatRatio(summary.averageRoas, 2) },
  ];

  return (
    <div className="dashboard-grid">
      <section className="kpi-grid" aria-label="Campaign KPIs">
        {kpis.map((kpi) => (
          <KpiCard key={kpi.label} label={kpi.label} value={kpi.value} />
        ))}
      </section>
      <section className="panel">
        <header className="panel-header">
          <h2>Daily spend trend</h2>
        </header>
        <CampaignTrendChart data={trend} currency={currency} />
      </section>
      <section className="panel map-panel">
        <header className="panel-header">
          <h2>Parish heatmap</h2>
          <p className="muted">Click a parish to filter the performance tables below.</p>
        </header>
        <ParishMap />
      </section>
      <section className="panel full-width">
        <CampaignTable rows={rows} currency={currency} />
      </section>
    </div>
  );
};

export default CampaignDashboard;
