import { useCallback, useId, useMemo, useState } from 'react';

import AgeDistributionBar from '../components/AgeDistributionBar';
import AgeGenderPyramid from '../components/AgeGenderPyramid';
import DashboardState from '../components/DashboardState';
import GenderDonut from '../components/GenderDonut';
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
  const { demographics, loadAll, lastSnapshotGeneratedAt } = useDashboardStore((state) => ({
    demographics: state.demographics,
    loadAll: state.loadAll,
    lastSnapshotGeneratedAt: state.lastSnapshotGeneratedAt,
  }));
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
  const liveDatasetBlocked =
    datasetMode === 'live' && liveReason && liveReason !== 'ready';
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
    const femaleRow = data.byGender.find((g) => g.gender.toLowerCase() === 'female');
    const femalePct = totalReach > 0 && femaleRow ? femaleRow.reach / totalReach : 0;

    const topAge = data.byAge.length > 0
      ? data.byAge.reduce(
          (best, row) => (row.impressions > best.impressions ? row : best),
          data.byAge[0],
        )
      : undefined;

    const totalImpressions = data.byAge.reduce((sum, a) => sum + a.impressions, 0);

    return [
      { label: 'Total reach', value: formatNumber(totalReach) },
      { label: '% Female', value: formatPercent(femalePct) },
      { label: 'Top age group', value: topAge?.ageRange ?? '—' },
      { label: 'Impressions', value: formatNumber(totalImpressions) },
    ];
  }, [demographics.data]);

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

  return pageShell(
    <div className="dashboardGrid">
      {/* KPI row */}
      <div className="kpiColumn" role="group" aria-label="Audience KPIs">
        {isLoading
          ? Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} height={72} borderRadius="0.75rem" />
            ))
          : kpis?.map((kpi) => (
              <StatCard key={kpi.label} label={kpi.label} value={kpi.value} />
            ))}
      </div>

      {/* Pyramid + Donut side by side */}
      <div className="audienceChartsRow">
        <Card title="Population pyramid" className="chartCard">
          {isLoading ? (
            <Skeleton height={320} borderRadius="1rem" />
          ) : data?.byAgeGender ? (
            <AgeGenderPyramid data={data.byAgeGender} metric="impressions" />
          ) : null}
        </Card>
        <Card title="Gender split" className="chartCard">
          {isLoading ? (
            <Skeleton height={260} borderRadius="1rem" />
          ) : data?.byGender ? (
            <GenderDonut data={data.byGender} metric="impressions" />
          ) : null}
        </Card>
      </div>

      {/* Age distribution with metric picker */}
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
        ) : data?.byAgeGender ? (
          <AgeDistributionBar data={data.byAgeGender} metric={distributionMetric} />
        ) : null}
      </Card>

      {/* Demographics detail table */}
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
