import { useCallback, useId, useMemo, type ReactNode } from 'react';
import { ResponsiveContainer } from 'recharts';

import CampaignTable from '../components/CampaignTable';
import CampaignTrendChart from '../components/CampaignTrendChart';
import DashboardState from '../components/DashboardState';
import ParishMap from '../components/ParishMap';
import RegionBreakdownTable from '../components/RegionBreakdownTable';
import Skeleton from '../components/Skeleton';
import StatusBanner from '../components/StatusBanner';
import Card from '../components/ui/Card';
import StatCard from '../components/ui/StatCard';
import { useAuth } from '../auth/AuthContext';
import { messageForLiveDatasetReason, titleForLiveDatasetReason } from '../lib/datasetStatus';
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
  const { campaign, campaignRows, parish, loadAll, lastSnapshotGeneratedAt, availability, coverage } =
    useDashboardStore((state) => ({
      campaign: state.campaign,
      campaignRows: state.getCampaignRowsForSelectedParish(),
      parish: state.parish,
      loadAll: state.loadAll,
      lastSnapshotGeneratedAt: state.lastSnapshotGeneratedAt,
      availability: state.availability,
      coverage: state.coverage,
    }));
  const datasetMode = useDatasetStore((state) => state.mode);
  const datasetSource = useDatasetStore((state) => state.source);
  const liveReason = useDatasetStore((state) => state.liveReason);
  const liveDetail = useDatasetStore((state) => state.liveDetail);
  const snapshotRelative = lastSnapshotGeneratedAt
    ? formatRelativeTime(lastSnapshotGeneratedAt)
    : null;
  const snapshotAbsolute = lastSnapshotGeneratedAt
    ? formatAbsoluteTime(lastSnapshotGeneratedAt)
    : null;
  const snapshotIsStale = isTimestampStale(lastSnapshotGeneratedAt, 60);
  const headingId = useId();
  const campaignAvailability = availability?.campaign;
  const parishCoverage = availability?.parish_map.coveragePercent ?? 0;
  const coverageLabel =
    coverage?.startDate && coverage?.endDate
      ? `${coverage.startDate} to ${coverage.endDate}`
      : null;

  const isInitialLoading = campaign.status === 'loading' && !campaign.data;
  const hasCampaignData = Boolean(campaign.data);
  const liveDatasetBlocked =
    datasetMode === 'live' && datasetSource === 'warehouse' && liveReason && liveReason !== 'ready';
  const liveDatasetMessage = liveReason
    ? messageForLiveDatasetReason(liveReason, liveDetail)
    : null;
  const shouldShowRegionBreakdown = (parish.data?.length ?? 0) > 0 || parish.status === 'loading';
  const shouldShowMap = parishCoverage > 0.6;

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
          tone={
            datasetMode === 'live' && liveReason === 'default_snapshot'
              ? 'warning'
              : datasetMode === 'live' && liveReason && liveReason !== 'ready'
                ? 'warning'
                : snapshotIsStale
                  ? 'warning'
                  : 'info'
          }
          message={
            datasetMode === 'live'
              ? liveDatasetBlocked
                ? liveDatasetMessage ?? 'Waiting for live snapshot...'
                : (snapshotRelative ?? 'Waiting for live snapshot...')
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
        label: 'Reach',
        value: summary ? formatNumber(summary.totalReach ?? 0) : '—',
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
        label: 'CTR',
        value: summary ? formatRatio(summary.ctr ?? 0, 2) : '—',
        sparkline: clicksSeries,
      },
      {
        label: 'CPC',
        value: summary ? formatCurrency(summary.cpc ?? 0, currency) : '—',
        sparkline: spendSeries,
      },
      {
        label: 'CPM',
        value: summary ? formatCurrency(summary.cpm ?? 0, currency) : '—',
        sparkline: impressionsSeries,
      },
      {
        label: 'CPA',
        value: summary ? formatCurrency(summary.cpa ?? 0, currency) : '—',
        sparkline: conversionsSeries,
      },
      {
        label: 'Frequency',
        value: summary ? formatRatio(summary.frequency ?? 0, 2) : '—',
        sparkline: impressionsSeries,
      },
      {
        label: 'Conv. / $',
        value: summary ? formatRatio(summary.averageRoas, 2) : '—',
        sparkline: roasSeries,
        tooltip: 'Conversion count divided by spend. Not revenue-based ROAS.',
      },
    ],
    [
      clicksSeries,
      conversionsSeries,
      currency,
      impressionsSeries,
      roasSeries,
      spendSeries,
      summary,
    ],
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
    if (liveDatasetBlocked) {
      return pageShell(
        <div className="dashboardGrid">
          <Card title={titleForLiveDatasetReason(liveReason)} className="chartCard">
            <DashboardState
              variant="empty"
              icon={<CampaignEmptyIcon />}
              message={liveDatasetMessage ?? 'Live warehouse metrics are unavailable.'}
              actionLabel="Refresh data"
              onAction={handleRetry}
              layout="compact"
            />
          </Card>
        </div>,
      );
    }
    const errorTitle =
      campaign.errorKind === 'stale_snapshot'
        ? 'Dashboard data is refreshing'
        : campaign.errorKind === 'network'
          ? 'Unable to connect'
          : 'Campaign insights';
    return pageShell(
      <div className="dashboardGrid">
        <Card title={errorTitle} className="chartCard">
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
    const emptyVariant = campaignAvailability?.reason === 'no_matching_filters' ? 'no-results' : 'empty';
    const emptyTitle =
      campaignAvailability?.reason === 'no_matching_filters'
        ? 'No campaign rows match this view'
        : campaignAvailability?.reason === 'no_recent_data'
          ? 'No recent reportable data'
          : 'No campaign insights yet';
    const emptyMessage =
      campaignAvailability?.reason === 'no_matching_filters'
        ? 'No campaign rows matched the selected client, range, or search filters.'
        : campaignAvailability?.reason === 'no_recent_data'
          ? 'The selected Meta account is connected, but Meta returned no recent reportable campaign results for this window.'
          : 'Campaign performance will appear once metrics are ingested for the selected Meta account.';
    return pageShell(
      <div className="dashboardGrid">
        <Card title="Campaign insights" className="chartCard">
          <DashboardState
            variant={emptyVariant}
            icon={<CampaignEmptyIcon />}
            title={emptyTitle}
            message={emptyMessage}
            actionLabel="Refresh data"
            onAction={handleRetry}
            layout="compact"
          />
        </Card>
      </div>,
    );
  }

  if (
    !isInitialLoading &&
    campaignAvailability?.status === 'empty' &&
    (campaign.data?.rows.length ?? 0) === 0
  ) {
    const emptyVariant = campaignAvailability.reason === 'no_matching_filters' ? 'no-results' : 'empty';
    const emptyTitle =
      campaignAvailability.reason === 'no_matching_filters'
        ? 'No campaign rows match this view'
        : campaignAvailability.reason === 'no_recent_data'
          ? 'No recent reportable data'
          : 'No campaign insights yet';
    const emptyMessage =
      campaignAvailability.reason === 'no_matching_filters'
        ? 'No campaign rows matched the selected client, range, or search filters.'
        : campaignAvailability.reason === 'no_recent_data'
          ? 'The selected Meta account is connected, but Meta returned no recent reportable campaign results for this window.'
          : 'Campaign performance will appear once metrics are ingested for the selected Meta account.';
    return pageShell(
      <div className="dashboardGrid">
        <Card title="Campaign insights" className="chartCard">
          <DashboardState
            variant={emptyVariant}
            icon={<CampaignEmptyIcon />}
            title={emptyTitle}
            message={emptyMessage}
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
            tooltip={kpi.tooltip}
          />
        ))}
      </div>

      <Card className="chartCard" title="Daily spend trend">
        {coverageLabel ? <p className="muted">Coverage: {coverageLabel}</p> : null}
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

      {shouldShowMap ? (
        <Card className="mapCard" title="Parish heatmap">
          <p className="muted">Click a parish to filter the performance tables below.</p>
          <div className="mapViewport">
            <ParishMap onRetry={handleRetry} />
          </div>
        </Card>
      ) : null}

      {shouldShowRegionBreakdown ? (
        <Card
          title="Region breakdown"
          className={shouldShowMap ? undefined : 'tableCardWide'}
        >
          <p className="muted">
            Parish coverage: {(parishCoverage * 100).toFixed(0)}%. Click a row to filter the
            performance tables below.
          </p>
          <RegionBreakdownTable onReload={handleRetry} />
        </Card>
      ) : null}

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
