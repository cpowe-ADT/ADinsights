import { useCallback, useId, useMemo, type ReactNode } from 'react';
import { ResponsiveContainer } from 'recharts';

import CampaignTable from '../components/CampaignTable';
import CampaignTrendChart from '../components/CampaignTrendChart';
import DashboardState from '../components/DashboardState';
import ParishMap from '../components/ParishMap';
import Skeleton from '../components/Skeleton';
import StatusBanner from '../components/StatusBanner';
import Card from '../components/ui/Card';
import StatCard from '../components/ui/StatCard';
import { useAuth } from '../auth/AuthContext';
import useDashboardStore from '../state/useDashboardStore';
import { useDatasetStore } from '../state/useDatasetStore';
import {
  formatAbsoluteTime,
  formatCurrency,
  formatNumber,
  formatRatio,
  formatRelativeTime,
  isTimestampStale,
} from '../lib/format';

import '../styles/dashboard.css';

type MetricSeries = Array<number | undefined>;

const sanitizeSeries = (series: MetricSeries): number[] =>
  series.filter((value): value is number => typeof value === 'number' && Number.isFinite(value));

const CampaignEmptyIcon = () => (
  <svg
    width="48"
    height="48"
    viewBox="0 0 48 48"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.4"
  >
    <rect x="10" y="16" width="6" height="18" rx="2" />
    <rect x="20" y="10" width="6" height="24" rx="2" />
    <rect x="30" y="20" width="6" height="14" rx="2" />
    <path d="M12 36h24" strokeLinecap="round" />
  </svg>
);

const TrendPlaceholderIcon = () => (
  <svg
    width="48"
    height="48"
    viewBox="0 0 48 48"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.2"
  >
    <path d="M10 32 20 20l8 8 10-16" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M10 36h28" strokeLinecap="round" />
    <circle cx="20" cy="20" r="2" fill="currentColor" stroke="none" />
    <circle cx="28" cy="28" r="2" fill="currentColor" stroke="none" />
    <circle cx="38" cy="12" r="2" fill="currentColor" stroke="none" />
  </svg>
);

const CampaignDashboard = () => {
  const { tenantId } = useAuth();
  const { campaign, campaignRows, loadAll, lastSnapshotGeneratedAt } = useDashboardStore((state) => ({
    campaign: state.campaign,
    campaignRows: state.getCampaignRowsForSelectedParish(),
    loadAll: state.loadAll,
    lastSnapshotGeneratedAt: state.lastSnapshotGeneratedAt,
  }));
  const datasetMode = useDatasetStore((state) => state.mode);
  const snapshotRelative = lastSnapshotGeneratedAt
    ? formatRelativeTime(lastSnapshotGeneratedAt)
    : null;
  const snapshotAbsolute = lastSnapshotGeneratedAt ? formatAbsoluteTime(lastSnapshotGeneratedAt) : null;
  const snapshotIsStale = isTimestampStale(lastSnapshotGeneratedAt, 60);
  const headingId = useId();

  const isInitialLoading = campaign.status === 'loading' && !campaign.data;
  const hasCampaignData = Boolean(campaign.data);

  const handleRetry = useCallback(() => {
    void loadAll(tenantId, { force: true });
  }, [loadAll, tenantId]);

  const pageShell = (content: ReactNode) => (
    <section className="dashboardPage" aria-labelledby={headingId}>
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Campaign dashboard</p>
        <h1 className="dashboardHeading" id={headingId}>
          Campaign performance
        </h1>
        <StatusBanner
          tone={snapshotIsStale ? 'warning' : 'info'}
          message={
            datasetMode === 'live'
              ? snapshotRelative ?? 'Waiting for live snapshot...'
              : snapshotRelative
              ? `Demo data - ${snapshotRelative}`
              : 'Demo dataset active'
          }
          title={snapshotAbsolute ?? undefined}
          ariaLabel="Snapshot status"
        />
      </header>
      {content}
    </section>
  );

  const summary = campaign.data?.summary;
  const trend = campaign.data?.trend;
  const currency = summary?.currency ?? 'USD';

  const {
    spendSeries,
    impressionsSeries,
    clicksSeries,
    conversionsSeries,
    roasSeries,
    hasTrendData,
    peakSpend,
    trendStart,
    trendEnd,
  } = useMemo(() => {
    const trendPoints = trend ?? [];
    if (trendPoints.length === 0) {
      return {
        spendSeries: [],
        impressionsSeries: [],
        clicksSeries: [],
        conversionsSeries: [],
        roasSeries: [],
        hasTrendData: false,
        peakSpend: 0,
        trendStart: null as Date | null,
        trendEnd: null as Date | null,
      };
    }

    const spend = sanitizeSeries(trendPoints.map((point) => point.spend));
    const impressions = sanitizeSeries(trendPoints.map((point) => point.impressions));
    const clicks = sanitizeSeries(trendPoints.map((point) => point.clicks));
    const conversions = sanitizeSeries(trendPoints.map((point) => point.conversions));
    const roas = sanitizeSeries(
      trendPoints.map((point) => {
        if (!point.spend) {
          return undefined;
        }

        const ratio = point.conversions / point.spend;
        return Number.isFinite(ratio) ? ratio : undefined;
      }),
    );

    return {
      spendSeries: spend,
      impressionsSeries: impressions,
      clicksSeries: clicks,
      conversionsSeries: conversions,
      roasSeries: roas,
      hasTrendData: true,
      peakSpend: Math.max(...trendPoints.map((point) => point.spend)),
      trendStart: new Date(trendPoints[0].date),
      trendEnd: new Date(trendPoints[trendPoints.length - 1].date),
    };
  }, [trend]);

  const kpis = useMemo(
    () => [
      {
        label: 'Spend',
        value: summary ? formatCurrency(summary.totalSpend, currency) : '—',
        sparkline: spendSeries,
      },
      {
        label: 'Impressions',
        value: summary ? formatNumber(summary.totalImpressions) : '—',
        sparkline: impressionsSeries,
      },
      {
        label: 'Clicks',
        value: summary ? formatNumber(summary.totalClicks) : '—',
        sparkline: clicksSeries,
      },
      {
        label: 'Conversions',
        value: summary ? formatNumber(summary.totalConversions) : '—',
        sparkline: conversionsSeries,
      },
      {
        label: 'Avg. ROAS',
        value: summary ? formatRatio(summary.averageRoas, 2) : '—',
        sparkline: roasSeries,
      },
    ],
    [clicksSeries, conversionsSeries, currency, impressionsSeries, roasSeries, spendSeries, summary],
  );

  const chartFooter = useMemo(() => {
    if (!hasTrendData || !trendStart || !trendEnd) {
      return null;
    }

    const dateRangeFormatter = new Intl.DateTimeFormat('en-JM', {
      month: 'short',
      day: 'numeric',
    });

    return (
      <div className="chartFooter">
        <div>
          <span>Peak daily spend</span>
          <strong>{formatCurrency(peakSpend, currency)}</strong>
        </div>
        <div className="chartFooterDates">
          <span>{dateRangeFormatter.format(trendStart)}</span>
          <span aria-hidden="true">–</span>
          <span>{dateRangeFormatter.format(trendEnd)}</span>
        </div>
      </div>
    );
  }, [currency, hasTrendData, peakSpend, trendEnd, trendStart]);

  if (campaign.status === 'error' && !hasCampaignData) {
    return pageShell(
      <div className="dashboardGrid">
        <Card title="Campaign insights" className="chartCard">
          <DashboardState
            variant="error"
            message={campaign.error ?? 'Unable to load campaign performance.'}
            actionLabel="Retry load"
            onAction={handleRetry}
            layout="compact"
          />
        </Card>
      </div>,
    );
  }

  if (!hasCampaignData && !isInitialLoading) {
    return pageShell(
      <div className="dashboardGrid">
        <Card title="Campaign insights" className="chartCard">
          <DashboardState
            variant="empty"
            icon={<CampaignEmptyIcon />}
            title="No campaign insights yet"
            message="Campaign performance will appear once metrics are ingested."
            actionLabel="Refresh data"
            onAction={handleRetry}
            layout="compact"
          />
        </Card>
      </div>,
    );
  }

  return pageShell(
    <div className="dashboardGrid">
      <div className="kpiColumn" role="group" aria-label="Campaign KPIs">
        {kpis.map((kpi) => (
          <StatCard
            key={kpi.label}
            label={kpi.label}
            value={kpi.value}
            sparkline={kpi.sparkline}
          />
        ))}
      </div>

      <Card className="chartCard" title="Daily spend trend">
        {isInitialLoading ? (
          <div className="widget-skeleton" aria-busy="true">
            <Skeleton height={220} borderRadius="1rem" />
            <Skeleton width="45%" height="0.85rem" />
          </div>
        ) : hasTrendData ? (
          <ResponsiveContainer width="100%" height="100%">
            <CampaignTrendChart data={trend ?? []} currency={currency} />
          </ResponsiveContainer>
        ) : (
          <DashboardState
            variant="empty"
            icon={<TrendPlaceholderIcon />}
            title="No trend data yet"
            message="Trend insights will appear once we have daily results."
            actionLabel="Refresh data"
            onAction={handleRetry}
            actionVariant="secondary"
            layout="compact"
          />
        )}
        {chartFooter}
      </Card>

      <Card className="mapCard" title="Parish heatmap">
        <p className="muted">Click a parish to filter the performance tables below.</p>
        <div className="mapViewport">
          <ParishMap onRetry={handleRetry} />
        </div>
      </Card>

      <Card title="Campaign metrics table" className="tableCardWide">
        <CampaignTable
          rows={campaignRows}
          currency={currency}
          isLoading={campaign.status === 'loading'}
          onReload={handleRetry}
        />
      </Card>
    </div>,
  );
};

export default CampaignDashboard;
