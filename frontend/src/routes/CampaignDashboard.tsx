import CampaignTable from "../components/CampaignTable";
import CampaignTrendChart from "../components/CampaignTrendChart";
import FullPageLoader from "../components/FullPageLoader";
import Metric, { MetricBadge, MetricDeltaDirection } from "../components/Metric";
import ParishMap from "../components/ParishMap";
import useDashboardStore from "../state/useDashboardStore";
import { formatCurrency, formatNumber, formatPercent, formatRatio } from "../lib/format";

function toTrend(values: number[] | undefined): number[] | undefined {
  if (!values || values.length === 0) {
    return undefined;
  }
  return values.map((value) => (Number.isFinite(value) ? Number(value) : 0));
}

function computeDelta(
  values: number[] | undefined,
  formatter: (value: number) => string = (value) => formatNumber(Math.abs(value))
): { delta?: string; direction: MetricDeltaDirection } {
  if (!values || values.length < 2) {
    return { direction: "neutral" };
  }

  const latest = values[values.length - 1];
  const previous = values[values.length - 2];

  if (!Number.isFinite(latest) || !Number.isFinite(previous)) {
    return { direction: "neutral" };
  }

  const change = latest - previous;

  if (change === 0) {
    return { direction: "neutral" };
  }

  if (previous !== 0) {
    const percent = Math.abs(change / previous);
    if (Number.isFinite(percent) && percent !== 0) {
      const direction: MetricDeltaDirection = change > 0 ? "up" : "down";
      const magnitude = formatPercent(percent, 1);
      return {
        direction,
        delta: `${direction === "down" ? "-" : "+"}${magnitude}`,
      };
    }
  }

  const direction: MetricDeltaDirection = change > 0 ? "up" : "down";
  return {
    direction,
    delta: `${change > 0 ? "+" : "-"}${formatter(Math.abs(change))}`,
  };
}

function resolveBadge(values: number[] | undefined, fallback?: MetricBadge): MetricBadge | undefined {
  if (!values || values.length === 0) {
    return fallback;
  }
  if (values.every((value) => value === 0)) {
    return "Paused";
  }
  if (values.length < 3) {
    return "New";
  }
  return fallback;
}

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

  const spendTrend = toTrend(trend.map((point) => point.spend));
  const impressionsTrend = toTrend(trend.map((point) => point.impressions));
  const clicksTrend = toTrend(trend.map((point) => point.clicks));
  const conversionsTrend = toTrend(trend.map((point) => point.conversions));
  const roasTrend = toTrend(
    trend.map((point) => {
      if (!point.spend) {
        return 0;
      }
      const value = point.conversions / point.spend;
      return Number.isFinite(value) ? value : 0;
    })
  );

  const spendDelta = computeDelta(spendTrend);
  const impressionsDelta = computeDelta(impressionsTrend);
  const clicksDelta = computeDelta(clicksTrend);
  const conversionsDelta = computeDelta(conversionsTrend);
  const roasDelta = computeDelta(roasTrend, (value) => formatRatio(Math.abs(value), 2));

  const conversionBadge: MetricBadge | undefined = summary.totalConversions < 10 ? "Limited data" : undefined;
  const spendBadge = resolveBadge(spendTrend, summary.totalSpend === 0 ? "Paused" : undefined);
  const impressionsBadge = resolveBadge(impressionsTrend);
  const roasBadge = resolveBadge(roasTrend);

  const metrics = [
    {
      label: "Spend",
      value: formatCurrency(summary.totalSpend, currency),
      delta: spendDelta.delta,
      deltaDirection: spendDelta.direction,
      hint: "Compared to the previous day",
      trend: spendTrend,
      badge: spendBadge,
    },
    {
      label: "Impressions",
      value: formatNumber(summary.totalImpressions),
      delta: impressionsDelta.delta,
      deltaDirection: impressionsDelta.direction,
      hint: "Daily impression volume",
      trend: impressionsTrend,
      badge: impressionsBadge,
    },
    {
      label: "Clicks",
      value: formatNumber(summary.totalClicks),
      delta: clicksDelta.delta,
      deltaDirection: clicksDelta.direction,
      hint: "Interactions captured",
      trend: clicksTrend,
    },
    {
      label: "Conversions",
      value: formatNumber(summary.totalConversions),
      delta: conversionsDelta.delta,
      deltaDirection: conversionsDelta.direction,
      hint: "Attributed results",
      trend: conversionsTrend,
      badge: conversionBadge,
    },
    {
      label: "Avg. ROAS",
      value: formatRatio(summary.averageRoas, 2),
      delta: roasDelta.delta,
      deltaDirection: roasDelta.direction,
      hint: "Return on ad spend",
      trend: roasTrend,
      badge: roasBadge,
    },
  ];

  return (
    <div className="dashboard-grid">
      <section className="metric-grid" aria-label="Campaign KPIs">
        {metrics.map((metric) => (
          <Metric
            key={metric.label}
            label={metric.label}
            value={metric.value}
            delta={metric.delta}
            deltaDirection={metric.deltaDirection}
            hint={metric.hint}
            trend={metric.trend}
            badge={metric.badge}
          />
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
        <CampaignTable rows={campaignRows} currency={currency} />
      </section>
    </div>
  );
};

export default CampaignDashboard;
