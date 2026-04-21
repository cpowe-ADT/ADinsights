import { useCallback, useId, useMemo } from 'react';

import DashboardState from '../components/DashboardState';
import StatusBanner from '../components/StatusBanner';
import Card from '../components/ui/Card';
import {
  AccessibleTableToggle,
  ChartSkeleton,
  DistributionBar,
  KpiTile,
  PieComposition,
  TrendLine,
  VizDataTable,
} from '../components/viz';
import type { TrendLinePoint } from '../components/viz/TrendLine';
import { useAuth } from '../auth/AuthContext';
import { messageForLiveDatasetReason, titleForLiveDatasetReason } from '../lib/datasetStatus';
import useDashboardStore from '../state/useDashboardStore';
import { useDatasetStore } from '../state/useDatasetStore';
import {
  formatAbsoluteTime,
  formatRelativeTime,
  isTimestampStale,
} from '../lib/format';
import { formatPlatformLabel, platformColor } from '../lib/platformLabels';
import {
  ctrFromRow,
  cpmFromRow,
  roasFromRow,
  totalsFromPlatformRows,
} from '../lib/combinedAggregates';

import '../styles/dashboard.css';

// FP-PLAT-03: The `formatPlatformLabel` helper previously lived at
// `PlatformDashboard.tsx:82–145`. Moved to `lib/platformLabels.ts` so
// CampaignDashboard + CreativeDashboard share the exact same slug→label
// contract (Sprint 2 top-2-by-spend label derivation preserved).

const EmptyIcon = () => (
  <svg
    width="48"
    height="48"
    viewBox="0 0 48 48"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.4"
  >
    <rect x="6" y="12" width="36" height="24" rx="3" />
    <path d="M6 20h36" />
    <path d="M18 12v24" />
  </svg>
);

type PlatformTableRow = {
  platform: string;
  label: string;
  color: string;
  spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  ctr: number;
  cpm: number;
  roas: number;
};

const PlatformDashboard = () => {
  const { tenantId } = useAuth();
  const { platforms, loadAll, lastSnapshotGeneratedAt } = useDashboardStore((state) => ({
    platforms: state.platforms,
    loadAll: state.loadAll,
    lastSnapshotGeneratedAt: state.lastSnapshotGeneratedAt,
  }));
  const datasetMode = useDatasetStore((state) => state.mode);
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

  const isLoading = platforms.status === 'loading' && !platforms.data;
  const hasData = Boolean(platforms.data);
  const liveDatasetBlocked =
    datasetMode === 'live' && liveReason && liveReason !== 'ready';
  const liveDatasetMessage = liveReason
    ? messageForLiveDatasetReason(liveReason, liveDetail)
    : null;

  const handleRetry = useCallback(() => {
    void loadAll(tenantId, { force: true });
  }, [loadAll, tenantId]);

  const totals = useMemo(() => {
    const data = platforms.data;
    if (!data) return null;
    return totalsFromPlatformRows(data.byPlatform);
  }, [platforms.data]);

  const platformRows = useMemo<PlatformTableRow[]>(() => {
    const data = platforms.data;
    if (!data) return [];
    return data.byPlatform.map((row) => ({
      platform: row.platform,
      label: formatPlatformLabel(row.platform),
      color: platformColor(row.platform),
      spend: row.spend,
      impressions: row.impressions,
      clicks: row.clicks,
      conversions: row.conversions,
      ctr: ctrFromRow(row),
      cpm: cpmFromRow(row),
      roas: roasFromRow(row),
    }));
  }, [platforms.data]);

  const deviceComposition = useMemo(() => {
    const data = platforms.data;
    if (!data) return [];
    return data.byDevice.map((row) => ({
      label: formatPlatformLabel(row.device),
      value: row.impressions,
    }));
  }, [platforms.data]);

  // [NEW-ENDPOINT] Per-platform daily trend series — sprints-plan §802 deferred.
  // CampaignTrendPoint has no `platform` field today, so the stacked-area upgrade
  // requires a new backend contract. Ship single-series TrendLine (blended spend)
  // as the interim per S4 architect-design §8.1 / §5 risk #7.
  const trendData = useMemo<TrendLinePoint[]>(() => {
    const data = platforms.data;
    if (!data) return [];
    // Derive a single blended-spend series per-device bucket date? We have no
    // time-series at this endpoint. Render an empty TrendLine placeholder so the
    // AccessibleTableToggle scaffold stays intact — `emptyReasonCode` handles
    // the "no data" messaging per viz-kit contract.
    return [];
  }, [platforms.data]);

  const pageShell = (content: React.ReactNode) => (
    <section className="dashboardPage" aria-labelledby={headingId}>
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Platforms</p>
        <h1 className="dashboardHeading" id={headingId}>
          Platform &amp; device performance
        </h1>
        <StatusBanner
          tone={
            datasetMode === 'live' && liveReason && liveReason !== 'ready'
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

  if (platforms.status === 'error' && !hasData) {
    if (liveDatasetBlocked) {
      return pageShell(
        <div className="dashboardGrid">
          <Card title={titleForLiveDatasetReason(liveReason)} className="chartCard">
            <DashboardState
              variant="empty"
              icon={<EmptyIcon />}
              message={liveDatasetMessage ?? 'Live platform data is unavailable.'}
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
        <Card title="Platform insights" className="chartCard">
          <DashboardState
            variant="error"
            message={platforms.error ?? 'Unable to load platform data.'}
            actionLabel="Retry load"
            onAction={handleRetry}
            layout="compact"
          />
        </Card>
      </div>,
    );
  }

  if (!hasData && !isLoading) {
    return pageShell(
      <div className="dashboardGrid">
        <Card title="Platform insights" className="chartCard">
          <DashboardState
            variant="empty"
            icon={<EmptyIcon />}
            title="No platform data yet"
            message="Platform and device breakdowns will appear once data is synced from Meta."
            actionLabel="Refresh data"
            onAction={handleRetry}
            layout="compact"
          />
        </Card>
      </div>,
    );
  }

  const data = platforms.data;

  // FP-PLAT-02: If the backend returned a populated platforms object but with
  // empty arrays, show an empty state rather than blank SVG charts.
  if (hasData && !isLoading && data?.byPlatform?.length === 0 && data?.byDevice?.length === 0) {
    return pageShell(
      <div className="dashboardGrid">
        <Card title="Platform insights" className="chartCard">
          <DashboardState
            variant="empty"
            icon={<EmptyIcon />}
            title="No platform data for selected range"
            message="Try a different date range or check that your Meta account has data synced."
            actionLabel="Refresh data"
            onAction={handleRetry}
            layout="compact"
          />
        </Card>
      </div>,
    );
  }

  // FP-PLAT-03: KPI tiles previously hardcoded "Facebook spend" / "Instagram spend".
  // When scope = google_ads only, those rows were always undefined and tiles showed "—".
  // Parameterize labels from the top-2 platforms by spend so the tiles reflect
  // whichever platforms the current scope actually returns (Meta, Google Ads, or both).
  const sortedPlatforms = data
    ? [...data.byPlatform].sort((a, b) => b.spend - a.spend)
    : [];
  const [topRow, secondRow] = sortedPlatforms;
  const firstLabel = topRow ? `${formatPlatformLabel(topRow.platform)} spend` : 'Top platform spend';
  const secondLabel = secondRow
    ? `${formatPlatformLabel(secondRow.platform)} spend`
    : 'Second platform spend';

  return pageShell(
    <div className="dashboardGrid">
      {/* KPI strip — 5 cross-platform tiles (FP-PLAT-03 top-2 labels preserved) */}
      <div className="kpiColumn" role="group" aria-label="Platform KPIs">
        <KpiTile
          label="Total spend"
          value={totals ? totals.spend : null}
          format="currency"
          currency="USD"
          isLoading={isLoading}
          reasonCode="platform_total_spend"
        />
        <KpiTile
          label="Total impressions"
          value={totals ? totals.impressions : null}
          format="number"
          isLoading={isLoading}
          reasonCode="platform_total_impressions"
        />
        <KpiTile
          label="Total clicks"
          value={totals ? totals.clicks : null}
          format="number"
          isLoading={isLoading}
          reasonCode="platform_total_clicks"
        />
        <KpiTile
          label={firstLabel}
          value={topRow ? topRow.spend : null}
          format="currency"
          currency="USD"
          isLoading={isLoading}
          reasonCode="platform_top_spend"
        />
        <KpiTile
          label={secondLabel}
          value={secondRow ? secondRow.spend : null}
          format="currency"
          currency="USD"
          isLoading={isLoading}
          reasonCode="platform_second_spend"
        />
      </div>

      {/* Platform legend — non-color encoding via explicit text label */}
      <Card title="Platform legend" className="chartCard">
        <ul
          aria-label="Platform color legend"
          style={{
            display: 'flex',
            gap: '1rem',
            listStyle: 'none',
            padding: 0,
            margin: 0,
            flexWrap: 'wrap',
          }}
        >
          {platformRows.map((row) => (
            <li
              key={row.platform}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
            >
              <span
                aria-hidden="true"
                style={{
                  display: 'inline-block',
                  width: '0.75rem',
                  height: '0.75rem',
                  borderRadius: '9999px',
                  background: row.color,
                }}
              />
              <span>{row.label}</span>
            </li>
          ))}
          {platformRows.length === 0 ? <li>Meta · Google Ads</li> : null}
        </ul>
      </Card>

      {/* Primary trend — single series (see [NEW-ENDPOINT] comment above) */}
      <Card title="Blended spend trend" className="chartCard">
        {isLoading ? (
          <ChartSkeleton height={260} variant="line" />
        ) : (
          <AccessibleTableToggle
            chartAriaLabel="Blended spend per day"
            chart={
              <TrendLine
                data={trendData}
                series={[{ key: 'spend', label: 'Spend' }]}
                yFormat="currency"
                currency="USD"
                ariaLabel="Blended spend per day"
                emptyReasonCode="no_platform_trend_series"
                height={260}
              />
            }
            table={
              <table>
                <caption>Blended spend per day</caption>
                <thead>
                  <tr>
                    <th scope="col">Date</th>
                    <th scope="col">Spend</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td colSpan={2}>
                      Per-platform daily series not yet available — deferred.
                    </td>
                  </tr>
                </tbody>
              </table>
            }
          />
        )}
      </Card>

      {/* Small-multiples — 2x2 DistributionBar grid */}
      <Card title="Platform comparison (small multiples)" className="chartCard">
        <div
          role="group"
          aria-label="Platform comparison small multiples"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
            gap: '1rem',
          }}
        >
          <div>
            <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '0.95rem' }}>Spend</h3>
            <DistributionBar
              data={platformRows.map((r) => ({
                label: r.label,
                value: r.spend,
                color: r.color,
              }))}
              yFormat="currency"
              currency="USD"
              ariaLabel="Spend by platform"
              isLoading={isLoading}
              emptyReasonCode="no_data_for_range"
              height={200}
            />
          </div>
          <div>
            <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '0.95rem' }}>Impressions</h3>
            <DistributionBar
              data={platformRows.map((r) => ({
                label: r.label,
                value: r.impressions,
                color: r.color,
              }))}
              yFormat="number"
              ariaLabel="Impressions by platform"
              isLoading={isLoading}
              emptyReasonCode="no_data_for_range"
              height={200}
            />
          </div>
          <div>
            <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '0.95rem' }}>Clicks</h3>
            <DistributionBar
              data={platformRows.map((r) => ({
                label: r.label,
                value: r.clicks,
                color: r.color,
              }))}
              yFormat="number"
              ariaLabel="Clicks by platform"
              isLoading={isLoading}
              emptyReasonCode="no_data_for_range"
              height={200}
            />
          </div>
          <div>
            <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '0.95rem' }}>Conversions</h3>
            <DistributionBar
              data={platformRows.map((r) => ({
                label: r.label,
                value: r.conversions,
                color: r.color,
              }))}
              yFormat="number"
              ariaLabel="Conversions by platform"
              isLoading={isLoading}
              emptyReasonCode="no_data_for_range"
              height={200}
            />
          </div>
        </div>
      </Card>

      {/* Composition — device split */}
      <Card title="Device split" className="chartCard">
        {isLoading ? (
          <ChartSkeleton height={260} variant="pie" />
        ) : (
          <PieComposition
            data={deviceComposition}
            yFormat="number"
            ariaLabel="Impressions by device"
            emptyReasonCode="no_data_for_range"
          />
        )}
      </Card>

      {/* Drill-down — platform-comparison table with color-coded chip */}
      <Card title="Platform & device detail" className="tableCardWide">
        <VizDataTable
          ariaLabel="Platform comparison"
          caption="Platform comparison"
          captionHidden
          csvFilename="platform-comparison.csv"
          data={platformRows}
          getRowId={(row) => row.platform}
          columns={[
            {
              accessorKey: 'label',
              header: 'Platform',
              cell: ({ row }) => (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span
                    aria-hidden="true"
                    style={{
                      display: 'inline-block',
                      width: '0.6rem',
                      height: '0.6rem',
                      borderRadius: '9999px',
                      background: row.original.color,
                    }}
                  />
                  {row.original.label}
                </span>
              ),
            },
            {
              accessorKey: 'spend',
              header: 'Spend',
              cell: ({ getValue }) =>
                Number(getValue()).toLocaleString(undefined, {
                  style: 'currency',
                  currency: 'USD',
                }),
            },
            {
              accessorKey: 'impressions',
              header: 'Impressions',
              cell: ({ getValue }) => Number(getValue()).toLocaleString(),
            },
            {
              accessorKey: 'clicks',
              header: 'Clicks',
              cell: ({ getValue }) => Number(getValue()).toLocaleString(),
            },
            {
              accessorKey: 'conversions',
              header: 'Conversions',
              cell: ({ getValue }) => Number(getValue()).toLocaleString(),
            },
            {
              accessorKey: 'ctr',
              header: 'CTR',
              cell: ({ getValue }) => `${(Number(getValue()) * 100).toFixed(2)}%`,
            },
            {
              accessorKey: 'cpm',
              header: 'CPM',
              cell: ({ getValue }) =>
                Number(getValue()).toLocaleString(undefined, {
                  style: 'currency',
                  currency: 'USD',
                }),
            },
            {
              accessorKey: 'roas',
              header: 'Conv. / $',
              cell: ({ getValue }) => Number(getValue()).toFixed(2),
            },
          ]}
        />
      </Card>
    </div>,
  );
};

export default PlatformDashboard;
