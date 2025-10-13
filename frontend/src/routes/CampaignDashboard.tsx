import { useCallback } from "react";

import CampaignTable from "../components/CampaignTable";
import CampaignTrendChart from "../components/CampaignTrendChart";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import KpiCard from "../components/KpiCard";
import ParishMap from "../components/ParishMap";
import Skeleton from "../components/Skeleton";
import { useAuth } from "../auth/AuthContext";
import useDashboardStore from "../state/useDashboardStore";
import { formatCurrency, formatNumber, formatRatio } from "../lib/format";

const CampaignEmptyIcon = () => (
  <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="2.4">
    <rect x="10" y="16" width="6" height="18" rx="2" />
    <rect x="20" y="10" width="6" height="24" rx="2" />
    <rect x="30" y="20" width="6" height="14" rx="2" />
    <path d="M12 36h24" strokeLinecap="round" />
  </svg>
);

const TrendPlaceholderIcon = () => (
  <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="2.2">
    <path d="M10 32 20 20l8 8 10-16" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M10 36h28" strokeLinecap="round" />
    <circle cx="20" cy="20" r="2" fill="currentColor" stroke="none" />
    <circle cx="28" cy="28" r="2" fill="currentColor" stroke="none" />
    <circle cx="38" cy="12" r="2" fill="currentColor" stroke="none" />
  </svg>
);

const CampaignDashboard = () => {
  const { tenantId } = useAuth();
  const { campaign, campaignRows, loadAll } = useDashboardStore((state) => ({
    campaign: state.campaign,
    campaignRows: state.getCampaignRowsForSelectedParish(),
    loadAll: state.loadAll,
  }));

  const isInitialLoading = campaign.status === "loading" && !campaign.data;
  const hasCampaignData = Boolean(campaign.data);

  const handleRetry = useCallback(() => {
    void loadAll(tenantId, { force: true });
  }, [loadAll, tenantId]);

  if (campaign.status === "error" && !hasCampaignData) {
    return (
      <div className="dashboard-grid single-panel">
        <ErrorState
          message={campaign.error ?? "Unable to load campaign performance."}
          onRetry={handleRetry}
          retryLabel="Retry load"
        />
      </div>
    );
  }

  if (!hasCampaignData && !isInitialLoading) {
    return (
      <div className="dashboard-grid single-panel">
        <EmptyState
          icon={<CampaignEmptyIcon />}
          title="No campaign insights yet"
          message="Campaign performance will appear once metrics are ingested."
          actionLabel="Refresh data"
          onAction={handleRetry}
        />
      </div>
    );
  }

  const summary = campaign.data?.summary;
  const trend = campaign.data?.trend ?? [];
  const currency = summary?.currency ?? "USD";

  const kpis = [
    { label: "Spend", value: summary ? formatCurrency(summary.totalSpend, currency) : "—" },
    { label: "Impressions", value: summary ? formatNumber(summary.totalImpressions) : "—" },
    { label: "Clicks", value: summary ? formatNumber(summary.totalClicks) : "—" },
    { label: "Conversions", value: summary ? formatNumber(summary.totalConversions) : "—" },
    { label: "Avg. ROAS", value: summary ? formatRatio(summary.averageRoas, 2) : "—" },
  ];

  return (
    <div className="dashboard-grid">
      <section className="kpi-grid" aria-label="Campaign KPIs">
        {kpis.map((kpi) => (
          <KpiCard key={kpi.label} label={kpi.label} value={kpi.value} isLoading={isInitialLoading} />
        ))}
      </section>
      <section className="panel">
        <header className="panel-header">
          <h2>Daily spend trend</h2>
        </header>
        {isInitialLoading ? (
          <div className="widget-skeleton" aria-busy="true">
            <Skeleton height={220} borderRadius="1rem" />
            <Skeleton width="45%" height="0.85rem" />
          </div>
        ) : trend.length > 0 ? (
          <CampaignTrendChart data={trend} currency={currency} />
        ) : (
          <EmptyState
            icon={<TrendPlaceholderIcon />}
            title="No trend data yet"
            message="Trend insights will appear once we have daily results."
            actionLabel="Refresh data"
            onAction={handleRetry}
            actionVariant="secondary"
          />
        )}
      </section>
      <section className="panel map-panel">
        <header className="panel-header">
          <h2>Parish heatmap</h2>
          <p className="muted">Click a parish to filter the performance tables below.</p>
        </header>
        <ParishMap onRetry={handleRetry} />
      </section>
      <section className="panel full-width">
        <CampaignTable
          rows={campaignRows}
          currency={currency}
          isLoading={campaign.status === "loading"}
          onReload={handleRetry}
        />
      </section>
    </div>
  );
};

export default CampaignDashboard;
