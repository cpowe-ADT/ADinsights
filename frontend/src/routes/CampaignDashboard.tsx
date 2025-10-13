import { useCallback } from "react";

import CampaignTable from "../components/CampaignTable";
import CampaignTrendChart from "../components/CampaignTrendChart";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import ChartCard from "../components/ChartCard";
import Metric from "../components/Metric";
import ParishMap from "../components/ParishMap";
import Skeleton from "../components/Skeleton";
import { useAuth } from "../auth/AuthContext";
import useDashboardStore from "../state/useDashboardStore";
import { formatCurrency, formatNumber, formatRatio } from "../lib/format";

type MetricBadge = "New" | "Paused" | "Limited data";

const sanitizeSeries = (series: Array<number | undefined>): number[] =>
  series.filter((value): value is number => typeof value === "number" && Number.isFinite(value));

const computeDeltaFromSeries = (
  series?: number[],
): { delta?: string; deltaDirection: "up" | "down" | "flat" } => {
  if (!series || series.length < 2) {
    return { delta: undefined, deltaDirection: "flat" };
  }

  const current = series[series.length - 1];
  const previous = series[series.length - 2];

  if (!Number.isFinite(current) || !Number.isFinite(previous) || previous === 0) {
    return { delta: undefined, deltaDirection: "flat" };
  }

  const change = ((current - previous) / Math.abs(previous)) * 100;

  if (!Number.isFinite(change)) {
    return { delta: undefined, deltaDirection: "flat" };
  }

  const direction = change === 0 ? "flat" : change > 0 ? "up" : "down";
  const magnitude = Math.abs(change);
  const formatted = `${change > 0 ? "+" : change < 0 ? "-" : ""}${magnitude >= 100 ? magnitude.toFixed(0) : magnitude.toFixed(1)}%`;

  return { delta: formatted, deltaDirection: direction };
};

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

  const spendSeries = sanitizeSeries(trend.map((point) => point.spend));
  const impressionsSeries = sanitizeSeries(trend.map((point) => point.impressions));
  const clicksSeries = sanitizeSeries(trend.map((point) => point.clicks));
  const conversionsSeries = sanitizeSeries(trend.map((point) => point.conversions));
  const roasSeries = sanitizeSeries(
    trend.map((point) => {
      if (!point.spend) {
        return undefined;
      }

      const ratio = point.conversions / point.spend;
      return Number.isFinite(ratio) ? ratio : undefined;
    }),
  );

  const baseBadge: MetricBadge | undefined = isInitialLoading
    ? undefined
    : !hasTrendData
    ? "Limited data"
    : trend.length <= 3
    ? "New"
    : undefined;
  const spendBadge: MetricBadge | undefined = summary && summary.totalSpend === 0 ? "Paused" : baseBadge;

  const kpis = [
    {
      label: "Spend",
      value: summary ? formatCurrency(summary.totalSpend, currency) : "—",
      trend: spendSeries,
      badge: spendBadge,
    },
    {
      label: "Impressions",
      value: summary ? formatNumber(summary.totalImpressions) : "—",
      trend: impressionsSeries,
      badge: baseBadge,
    },
    {
      label: "Clicks",
      value: summary ? formatNumber(summary.totalClicks) : "—",
      trend: clicksSeries,
      badge: baseBadge,
    },
    {
      label: "Conversions",
      value: summary ? formatNumber(summary.totalConversions) : "—",
      trend: conversionsSeries,
      badge: baseBadge,
    },
    {
      label: "Avg. ROAS",
      value: summary ? formatRatio(summary.averageRoas, 2) : "—",
      trend: roasSeries,
      badge: baseBadge,
      hint: summary ? "Return on ad spend across the selected period." : undefined,
    },
  ].map((metric) => {
    const { delta, deltaDirection } = computeDeltaFromSeries(metric.trend);

    return {
      ...metric,
      delta,
      deltaDirection,
      hint: metric.hint ?? (delta ? "vs previous day" : undefined),
    };
  });

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
          <Metric
            key={kpi.label}
            label={kpi.label}
            value={kpi.value}
            delta={kpi.delta}
            deltaDirection={kpi.deltaDirection}
            hint={kpi.hint}
            trend={kpi.trend}
            badge={kpi.badge}
          />
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
      <ChartCard title="Daily spend trend" footer={chartFooter}>
        <CampaignTrendChart data={trend} currency={currency} />
      </ChartCard>
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
