import { useCallback, useId, useMemo, useState } from 'react';

import AgeGenderPyramid from '../components/AgeGenderPyramid';
import DashboardState from '../components/DashboardState';
import Skeleton from '../components/Skeleton';
import StatusBanner from '../components/StatusBanner';
import Card from '../components/ui/Card';
import {
  AccessibleTableToggle,
  DistributionBar,
  KpiTile,
  PieComposition,
} from '../components/viz';
import { PLATFORM_CHART_TOKENS } from '../styles/chartTheme';
import { useAuth } from '../auth/AuthContext';
import { messageForLiveDatasetReason, titleForLiveDatasetReason } from '../lib/datasetStatus';
import useDashboardStore from '../state/useDashboardStore';
import { useDatasetStore } from '../state/useDatasetStore';
import {
  formatAbsoluteTime,
  formatNumber,
  formatRelativeTime,
  isTimestampStale,
} from '../lib/format';

import '../styles/dashboard.css';

type DistributionMetric = 'spend' | 'impressions' | 'clicks' | 'conversions';

const METRIC_OPTIONS: { value: DistributionMetric; label: string }[] = [
  { value: 'impressions', label: 'Impressions' },
  { value: 'spend', label: 'Spend' },
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
    <circle cx="24" cy="18" r="7" />
    <path d="M12 38c0-6.627 5.373-12 12-12s12 5.373 12 12" strokeLinecap="round" />
  </svg>
);

const AudienceDashboard = () => {
  const { tenantId } = useAuth();
  const { demographics, platforms, loadAll, lastSnapshotGeneratedAt } = useDashboardStore(
    (state) => ({
      demographics: state.demographics,
      platforms: state.platforms,
      loadAll: state.loadAll,
      lastSnapshotGeneratedAt: state.lastSnapshotGeneratedAt,
    }),
  );
  const datasetMode = useDatasetStore((state) => state.mode);
  const liveReason = useDatasetStore((state) => state.liveReason);
  const liveDetail = useDatasetStore((state) => state.liveDetail);

  const [distributionMetric, setDistributionMetric] = useState<DistributionMetric>('impressions');

  const snapshotRelative = lastSnapshotGeneratedAt
    ? formatRelativeTime(lastSnapshotGeneratedAt)
    : null;
  const snapshotAbsolute = lastSnapshotGeneratedAt
    ? formatAbsoluteTime(lastSnapshotGeneratedAt)
    : null;
  const snapshotIsStale = isTimestampStale(lastSnapshotGeneratedAt, 60);
  const headingId = useId();

  const isLoading = demographics.status === 'loading' && !demographics.data;
  const hasData = Boolean(demographics.data);
  const datasetSource = useDatasetStore((state) => state.source);
  const liveDatasetBlocked =
    datasetMode === 'live' && datasetSource === 'warehouse' && liveReason && liveReason !== 'ready';
  const liveDatasetMessage = liveReason
    ? messageForLiveDatasetReason(liveReason, liveDetail)
    : null;

  const handleRetry = useCallback(() => {
    void loadAll(tenantId, { force: true });
  }, [loadAll, tenantId]);

  const kpis = useMemo(() => {
    const data = demographics.data;
    if (!data) return null;

    const totalReach = data.byGender.reduce((sum, g) => sum + g.reach, 0);

    const topAge = data.byAge.length > 0
      ? data.byAge.reduce(
          (best, row) => (row.impressions > best.impressions ? row : best),
          data.byAge[0],
        )
      : undefined;

    const totalImpressions = data.byAge.reduce((sum, a) => sum + a.impressions, 0);
    const avgFrequency = totalReach > 0 ? totalImpressions / totalReach : 0;

    // Top device comes from a different store slice (platforms.byDevice). If
    // platforms.data is absent we hide the tile entirely rather than show "—".
    let topDeviceLabel: string | null = null;
    let topDeviceImpressions: number | null = null;
    const devices = platforms?.data?.byDevice ?? [];
    if (devices.length > 0) {
      const top = devices.reduce(
        (best, row) => (row.impressions > best.impressions ? row : best),
        devices[0],
      );
      topDeviceLabel = top.device;
      topDeviceImpressions = top.impressions;
    }

    return {
      totalReach,
      avgFrequency,
      topAgeLabel: topAge?.ageRange ?? '—',
      topAgeImpressions: topAge?.impressions ?? 0,
      topDeviceLabel,
      topDeviceImpressions,
    };
  }, [demographics.data, platforms?.data]);

  const genderPieData = useMemo(() => {
    const rows = demographics.data?.byGender ?? [];
    const colors = ['#6366f1', '#ec4899', '#22c55e', '#a3a3a3'];
    return rows
      .filter((row) => row.reach > 0 || row.impressions > 0)
      .map((row, idx) => ({
        label: row.gender.charAt(0).toUpperCase() + row.gender.slice(1),
        value: row.reach > 0 ? row.reach : row.impressions,
        color: colors[idx % colors.length],
      }));
  }, [demographics.data]);

  const ageDistData = useMemo(() => {
    const rows = demographics.data?.byAge ?? [];
    return rows.map((row) => ({
      label: row.ageRange,
      value: Number(row[distributionMetric] ?? 0),
    }));
  }, [demographics.data, distributionMetric]);

  const deviceDistData = useMemo(() => {
    const rows = platforms?.data?.byDevice ?? [];
    return rows.map((row) => ({
      label: row.device.charAt(0).toUpperCase() + row.device.slice(1),
      value: row.impressions,
    }));
  }, [platforms?.data]);

  const pageShell = (content: React.ReactNode) => (
    <section className="dashboardPage" aria-labelledby={headingId}>
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Audience</p>
        <h1 className="dashboardHeading" id={headingId}>
          Audience demographics
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

  if (demographics.status === 'error' && !hasData) {
    if (liveDatasetBlocked) {
      return pageShell(
        <div className="dashboardGrid">
          <Card title={titleForLiveDatasetReason(liveReason)} className="chartCard">
            <DashboardState
              variant="empty"
              icon={<EmptyIcon />}
              message={liveDatasetMessage ?? 'Live demographic data is unavailable.'}
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
        <Card title="Audience insights" className="chartCard">
          <DashboardState
            variant="error"
            message={demographics.error ?? 'Unable to load demographic data.'}
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
        <Card title="Audience insights" className="chartCard">
          <DashboardState
            variant="empty"
            icon={<EmptyIcon />}
            title="No demographic data yet"
            message="Audience demographics will appear once age/gender breakdowns are synced from Meta."
            actionLabel="Refresh data"
            onAction={handleRetry}
            layout="compact"
          />
        </Card>
      </div>,
    );
  }

  const data = demographics.data;

  // FP-AUD-01: If the backend returned a populated demographics object but with
  // empty age/gender arrays, show an empty state rather than null charts.
  if (hasData && !isLoading && !data?.byAgeGender?.length && !data?.byGender?.length) {
    return pageShell(
      <div className="dashboardGrid">
        <Card title="Audience insights" className="chartCard">
          <DashboardState
            variant="empty"
            icon={<EmptyIcon />}
            title="No demographic data for selected range"
            message="Try a different date range or check that age/gender breakdowns are synced from Meta."
            actionLabel="Refresh data"
            onAction={handleRetry}
            layout="compact"
          />
        </Card>
      </div>,
    );
  }

  const showTopDeviceTile = kpis?.topDeviceLabel !== null && kpis?.topDeviceLabel !== undefined;
  const showDeviceBlock = (platforms?.data?.byDevice?.length ?? 0) > 0;

  return pageShell(
    <div className="dashboardGrid">
      {/* Block 1 — KPI strip */}
      <div className="kpiColumn" role="group" aria-label="Audience KPIs">
        {isLoading ? (
          Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} height={72} borderRadius="0.75rem" />
          ))
        ) : kpis ? (
          <>
            <KpiTile label="Total reach" value={kpis.totalReach} format="number" />
            <KpiTile
              label="Avg frequency"
              value={kpis.avgFrequency > 0 ? kpis.avgFrequency : null}
              format="number"
              hint="Impressions ÷ reach"
            />
            <KpiTile
              label="Top age group"
              value={kpis.topAgeImpressions}
              format="number"
              hint={kpis.topAgeLabel}
            />
            {showTopDeviceTile ? (
              <KpiTile
                label="Top device"
                value={kpis.topDeviceImpressions}
                format="number"
                hint={kpis.topDeviceLabel ?? undefined}
              />
            ) : null}
          </>
        ) : null}
      </div>

      {/* Block 2 — Population pyramid (existing Age×Gender drill-down) + Gender composition */}
      <div className="audienceChartsRow">
        <Card title="Population pyramid" className="chartCard">
          {isLoading ? (
            <Skeleton height={320} borderRadius="1rem" />
          ) : data?.byAgeGender ? (
            <AgeGenderPyramid
              data={data.byAgeGender}
              metric="impressions"
              ariaLabel="Population pyramid of impressions by age range and gender"
            />
          ) : null}
        </Card>
        <Card title="Gender split" className="chartCard">
          {isLoading ? (
            <Skeleton height={260} borderRadius="1rem" />
          ) : genderPieData.length > 0 ? (
            <PieComposition
              ariaLabel="Audience reach by gender"
              data={genderPieData}
              yFormat="number"
              emptyReasonCode="no_data_for_range"
            />
          ) : null}
        </Card>
      </div>

      {/* Block 3 — Age distribution with metric picker */}
      <Card
        title="Age distribution"
        className="chartCard tableCardWide"
        action={
          <select
            className="audienceMetricSelect"
            value={distributionMetric}
            onChange={(e) => setDistributionMetric(e.target.value as DistributionMetric)}
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
        ) : ageDistData.length > 0 ? (
          <AccessibleTableToggle
            chartAriaLabel="Age distribution"
            chart={
              <DistributionBar
                ariaLabel={`Audience ${distributionMetric} by age range`}
                data={ageDistData}
                yFormat={distributionMetric === 'spend' ? 'currency' : 'number'}
                emptyReasonCode="no_data_for_range"
              />
            }
            table={
              <table className="dashboard-table">
                <thead>
                  <tr>
                    <th>Age range</th>
                    <th>{distributionMetric}</th>
                  </tr>
                </thead>
                <tbody>
                  {ageDistData.map((row) => (
                    <tr key={row.label}>
                      <td>{row.label}</td>
                      <td>{formatNumber(row.value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            }
          />
        ) : null}
      </Card>

      {/* Block 4 — Device distribution (hidden when platforms.data absent) */}
      {showDeviceBlock ? (
        <Card title="Device distribution" className="chartCard tableCardWide">
          {isLoading ? (
            <Skeleton height={260} borderRadius="1rem" />
          ) : (
            <DistributionBar
              ariaLabel="Impressions by device"
              data={deviceDistData.map((row, idx) => ({
                ...row,
                color:
                  idx === 0
                    ? PLATFORM_CHART_TOKENS.meta_ads
                    : idx === 1
                      ? PLATFORM_CHART_TOKENS.google_ads
                      : undefined,
              }))}
              yFormat="number"
              emptyReasonCode="no_data_for_range"
            />
          )}
        </Card>
      ) : null}

      {/* Block 5 — Demographics detail table */}
      <Card title="Demographics detail" className="tableCardWide">
        {isLoading ? (
          <Skeleton height={200} borderRadius="1rem" />
        ) : data?.byAgeGender ? (
          <div className="audienceTableWrap">
            <table className="audienceTable">
              <thead>
                <tr>
                  <th>Age range</th>
                  <th>Gender</th>
                  <th>Impressions</th>
                  <th>Reach</th>
                  <th>Clicks</th>
                  <th>Spend</th>
                  <th>Conversions</th>
                  <th>CTR</th>
                </tr>
              </thead>
              <tbody>
                {data.byAgeGender.map((row) => {
                  const ctr =
                    row.impressions > 0
                      ? ((row.clicks / row.impressions) * 100).toFixed(2)
                      : '0.00';
                  return (
                    <tr key={`${row.ageRange}-${row.gender}`}>
                      <td>{row.ageRange}</td>
                      <td style={{ textTransform: 'capitalize' }}>{row.gender}</td>
                      <td>{formatNumber(row.impressions)}</td>
                      <td>{formatNumber(row.reach)}</td>
                      <td>{formatNumber(row.clicks)}</td>
                      <td>{formatNumber(row.spend)}</td>
                      <td>{formatNumber(row.conversions)}</td>
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

export default AudienceDashboard;
