import { useCallback, useId, useMemo, type ReactNode } from 'react';
import { ResponsiveContainer } from 'recharts';
import { useShallow } from 'zustand/react/shallow';

import CampaignTable from '../components/CampaignTable';
import CampaignTrendChart from '../components/CampaignTrendChart';
import DashboardState from '../components/DashboardState';
import ParishMap from '../components/ParishMap';
import RegionBreakdownTable from '../components/RegionBreakdownTable';
import Skeleton from '../components/Skeleton';
import StatusBanner from '../components/StatusBanner';
import Card from '../components/ui/Card';
import StatCard from '../components/ui/StatCard';
import { DistributionBar, KpiTile } from '../components/viz';
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
import { formatPlatformLabel, platformColor } from '../lib/platformLabels';
import { topNBy } from '../lib/combinedAggregates';

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
  const {
    campaign,
    parish,
    loadAll,
    lastSnapshotGeneratedAt,
    availability,
    coverage,
  } = useDashboardStore(
    useShallow((state) => ({
      campaign: state.campaign,
      parish: state.parish,
      loadAll: state.loadAll,
      lastSnapshotGeneratedAt: state.lastSnapshotGeneratedAt,
      availability: state.availability,
      coverage: state.coverage,
    })),
  );
  const campaignRows = useDashboardStore(
    useShallow((state) => state.getCampaignRowsForSelectedParish()),
  );
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
                ? (liveDatasetMessage ?? 'Waiting for live snapshot...')
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

  // S4a: Cross-platform KPI strip (kit primitives). Architect §8.2 — simplified
  // 4-tile set complementing the legacy 11-StatCard detail row. Uses KpiTile
  // format-aware rendering so currency/decimal formatting is driven by the
  // viz kit.
  const crossPlatformKpis = useMemo(
    () => [
      { label: 'Total spend', value: summary?.totalSpend ?? null, format: 'currency' as const },
      { label: 'Total clicks', value: summary?.totalClicks ?? null, format: 'number' as const },
      {
        label: 'Total conversions',
        value: summary?.totalConversions ?? null,
        format: 'number' as const,
      },
      { label: 'Blended ROAS', value: summary?.averageRoas ?? null, format: 'rate' as const },
    ],
    [summary],
  );

  // Top-10 campaigns by spend — DistributionBar block per architect §8.2.
  // Platform color comes from PLATFORM_CHART_TOKENS via `platformColor()`.
  const topCampaignBars = useMemo(
    () =>
      topNBy(campaignRows, (row) => row.spend, 10).map((row) => ({
        label: row.name,
        value: row.spend,
        color: platformColor(row.platform),
      })),
    [campaignRows],
  );

  // Deduped platform-color legend for the KPI header — paired with the
  // shared helper so CampaignDashboard + CreativeDashboard + PlatformDashboard
  // all render the same chips.
  const platformLegend = useMemo(() => {
    const seen = new Map<string, string>();
    for (const row of campaignRows) {
      const slug = (row.platform || '').toLowerCase();
      if (slug && !seen.has(slug)) {
        seen.set(slug, platformColor(row.platform));
      }
    }
    return Array.from(seen.entries()).map(([platform, color]) => ({
      platform,
      label: formatPlatformLabel(platform),
      color,
    }));
  }, [campaignRows]);

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

  // FP-CAMP-02: Consolidated empty-state guard covering:
  //  1. No data object at all (!hasCampaignData)
  //  2. Data object present but rows=[] with availability.status='empty'
  //  3. Gap case previously missed: data object present, rows=[], but
  //     availability.status='available' (e.g. backend returned an empty rows
  //     array without setting availability to 'empty'). Treat this as empty too
  //     rather than rendering an empty CampaignTable silently.
  const campaignRowCount = campaign.data?.rows.length ?? 0;
  const hasNoCampaignRows = !hasCampaignData || campaignRowCount === 0;
  if (!isInitialLoading && hasNoCampaignRows) {
    const availabilityReason = campaignAvailability?.reason ?? null;
    const availableButEmpty =
      hasCampaignData && campaignRowCount === 0 && campaignAvailability?.status === 'available';
    const treatAsFiltered = availabilityReason === 'no_matching_filters' || availableButEmpty;
    const emptyVariant = treatAsFiltered ? 'no-results' : 'empty';
    const emptyTitle = treatAsFiltered
      ? 'No campaign rows match this view'
      : availabilityReason === 'no_recent_data'
        ? 'No recent reportable data'
        : 'No campaign insights yet';
    const emptyMessage = treatAsFiltered
      ? 'No campaign rows matched the selected client, range, or search filters.'
      : availabilityReason === 'no_recent_data'
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

      {/* S4a: Cross-platform KpiTile strip (kit primitive) alongside legacy detail row */}
      <div className="kpiColumn" role="group" aria-label="Cross-platform KPIs">
        {crossPlatformKpis.map((kpi) => (
          <KpiTile
            key={kpi.label}
            label={kpi.label}
            value={kpi.value}
            format={kpi.format}
            currency={currency}
            reasonCode={`campaign_${kpi.label.toLowerCase().replace(/\s+/g, '_')}`}
          />
        ))}
      </div>

      {/* S4a: Platform color legend — non-color text encoding for WCAG */}
      {platformLegend.length > 0 ? (
        <Card title="Platforms" className="chartCard">
          <ul
            aria-label="Campaign platform legend"
            style={{
              display: 'flex',
              gap: '1rem',
              listStyle: 'none',
              padding: 0,
              margin: 0,
              flexWrap: 'wrap',
            }}
          >
            {platformLegend.map((item) => (
              <li
                key={item.platform}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
              >
                <span
                  aria-hidden="true"
                  style={{
                    display: 'inline-block',
                    width: '0.75rem',
                    height: '0.75rem',
                    borderRadius: '9999px',
                    background: item.color,
                  }}
                />
                <span>{item.label}</span>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {/* [NEW-ENDPOINT] Per-platform daily series for stacked-area trend —
          sprints-plan §802 deferred: CampaignTrendPoint lacks a `platform`
          field (see S4-architect-design §5 risk #7 + §8.2). Keep single-
          series CampaignTrendChart until backend ships per-platform series. */}
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
        <Card title="Region breakdown" className="tableCardWide">
          <p className="muted">
            Parish coverage: {(parishCoverage * 100).toFixed(0)}%. Click a row to filter the
            performance tables below.
          </p>
          <RegionBreakdownTable onReload={handleRetry} />
        </Card>
      ) : null}

      {/* S4a: Top-10 campaigns by spend — DistributionBar from viz kit. */}
      {topCampaignBars.length > 0 ? (
        <Card title="Top campaigns by spend" className="chartCard">
          <DistributionBar
            data={topCampaignBars}
            yFormat="currency"
            currency={currency}
            ariaLabel="Top 10 campaigns by spend"
            isLoading={campaign.status === 'loading' && !hasCampaignData}
            emptyReasonCode="no_data_for_range"
            height={280}
          />
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
