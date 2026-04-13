import { useCallback, useId, useMemo, useState } from 'react';

import DashboardState from '../components/DashboardState';
import DeviceDonut from '../components/DeviceDonut';
import PlatformComparisonBars from '../components/PlatformComparisonBars';
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
  formatNumber,
  formatPercent,
  formatRelativeTime,
  isTimestampStale,
} from '../lib/format';

import '../styles/dashboard.css';

type BarMetric = 'spend' | 'impressions' | 'clicks' | 'conversions';

const METRIC_OPTIONS: { value: BarMetric; label: string }[] = [
  { value: 'spend', label: 'Spend' },
  { value: 'impressions', label: 'Impressions' },
  { value: 'clicks', label: 'Clicks' },
  { value: 'conversions', label: 'Conversions' },
];

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

  const [barMetric, setBarMetric] = useState<BarMetric>('spend');

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

  const kpis = useMemo(() => {
    const data = platforms.data;
    if (!data) return null;

    const fbRow = data.byPlatform.find(
      (p) => p.platform.toLowerCase() === 'facebook',
    );
    const igRow = data.byPlatform.find(
      (p) => p.platform.toLowerCase() === 'instagram',
    );

    const totalImpressions = data.byDevice.reduce(
      (sum, d) => sum + d.impressions,
      0,
    );
    const mobileImpressions = data.byDevice
      .filter((d) =>
        d.device.toLowerCase().startsWith('mobile'),
      )
      .reduce((sum, d) => sum + d.impressions, 0);
    const mobilePct =
      totalImpressions > 0 ? mobileImpressions / totalImpressions : 0;

    const topPlatform =
      data.byPlatform.length > 0
        ? data.byPlatform.reduce((best, row) =>
            row.conversions > best.conversions ? row : best,
          )
        : undefined;

    return [
      {
        label: 'Facebook spend',
        value: fbRow ? formatNumber(fbRow.spend) : '—',
      },
      {
        label: 'Instagram spend',
        value: igRow ? formatNumber(igRow.spend) : '—',
      },
      { label: 'Mobile %', value: formatPercent(mobilePct) },
      {
        label: 'Top platform',
        value: topPlatform?.platform ?? '—',
      },
    ];
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

  return pageShell(
    <div className="dashboardGrid">
      {/* KPI row */}
      <div className="kpiColumn" role="group" aria-label="Platform KPIs">
        {isLoading
          ? Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} height={72} borderRadius="0.75rem" />
            ))
          : kpis?.map((kpi) => (
              <StatCard key={kpi.label} label={kpi.label} value={kpi.value} />
            ))}
      </div>

      {/* Platform bars + Device donut side by side */}
      <div className="platformChartsRow">
        <Card
          title="Platform comparison"
          className="chartCard"
          action={
            <select
              className="audienceMetricSelect"
              value={barMetric}
              onChange={(e) => setBarMetric(e.target.value as BarMetric)}
              aria-label="Select metric"
            >
              {METRIC_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          }
        >
          {isLoading ? (
            <Skeleton height={300} borderRadius="1rem" />
          ) : data?.byPlatform ? (
            <PlatformComparisonBars data={data.byPlatform} metric={barMetric} />
          ) : null}
        </Card>
        <Card title="Device split" className="chartCard">
          {isLoading ? (
            <Skeleton height={260} borderRadius="1rem" />
          ) : data?.byDevice ? (
            <DeviceDonut data={data.byDevice} metric="impressions" />
          ) : null}
        </Card>
      </div>

      {/* Platform x Device detail table */}
      <Card title="Platform & device detail" className="tableCardWide">
        {isLoading ? (
          <Skeleton height={200} borderRadius="1rem" />
        ) : data?.byPlatformDevice ? (
          <div className="audienceTableWrap">
            <table className="audienceTable">
              <thead>
                <tr>
                  <th>Platform</th>
                  <th>Device</th>
                  <th>Impressions</th>
                  <th>Reach</th>
                  <th>Clicks</th>
                  <th>Spend</th>
                  <th>Conversions</th>
                  <th>CPC</th>
                  <th>CTR</th>
                </tr>
              </thead>
              <tbody>
                {data.byPlatformDevice.map((row) => {
                  const cpc =
                    row.clicks > 0
                      ? (row.spend / row.clicks).toFixed(2)
                      : '0.00';
                  const ctr =
                    row.impressions > 0
                      ? ((row.clicks / row.impressions) * 100).toFixed(2)
                      : '0.00';
                  return (
                    <tr key={`${row.platform}-${row.device}`}>
                      <td style={{ textTransform: 'capitalize' }}>{row.platform}</td>
                      <td style={{ textTransform: 'capitalize' }}>{row.device}</td>
                      <td>{formatNumber(row.impressions)}</td>
                      <td>{formatNumber(row.reach)}</td>
                      <td>{formatNumber(row.clicks)}</td>
                      <td>{formatNumber(row.spend)}</td>
                      <td>{formatNumber(row.conversions)}</td>
                      <td>{cpc}</td>
                      <td>{ctr}%</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </Card>
    </div>,
  );
};

export default PlatformDashboard;
