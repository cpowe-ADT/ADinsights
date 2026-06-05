import { useCallback, useMemo } from 'react';

import CreativeTable from '../components/CreativeTable';
import DashboardState from '../components/DashboardState';
import Card from '../components/ui/Card';
import {
  BubbleScatter,
  ChartSkeleton,
  KpiTile,
  PieComposition,
  VizDataTable,
} from '../components/viz';
import type { BubbleScatterDatum } from '../components/viz/BubbleScatter';
import { useAuth } from '../auth/AuthContext';
import { messageForLiveDatasetReason, titleForLiveDatasetReason } from '../lib/datasetStatus';
import { formatCurrency, formatNumber } from '../lib/format';
import { formatPlatformLabel, platformColor } from '../lib/platformLabels';
import useDashboardStore from '../state/useDashboardStore';
import { useDatasetStore } from '../state/useDatasetStore';

const CreativeEmptyIcon = () => (
  <svg
    width="48"
    height="48"
    viewBox="0 0 48 48"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.2"
  >
    <rect x="10" y="12" width="28" height="20" rx="3" />
    <path d="M16 18h16M16 24h10" strokeLinecap="round" />
    <circle cx="32" cy="26" r="4" />
    <path d="m34.5 28.5 5 5" strokeLinecap="round" />
  </svg>
);

type CreativeDrillRow = {
  id: string;
  name: string;
  platform: string;
  platformLabel: string;
  platformColor: string;
  spend: number;
  impressions: number;
  clicks: number;
  ctr: number;
  cpm: number;
  reach: number;
};

const CreativeDashboard = () => {
  const { tenantId } = useAuth();
  const { creative, campaign, creativeRows, availability, accountId } = useDashboardStore(
    (state) => ({
      creative: state.creative,
      campaign: state.campaign,
      creativeRows: state.getCreativeRowsForSelectedParish(),
      availability: state.availability,
      accountId: state.filters?.accountId ?? '',
    }),
  );
  const loadAll = useDashboardStore((state) => state.loadAll);
  const datasetMode = useDatasetStore((state) => state.mode);
  const datasetSource = useDatasetStore((state) => state.source);
  const liveReason = useDatasetStore((state) => state.liveReason);
  const liveDetail = useDatasetStore((state) => state.liveDetail);

  const currency = campaign.data?.summary.currency ?? 'USD';
  const creativeAvailability = availability?.creative;
  const liveDatasetBlocked =
    datasetMode === 'live' && datasetSource === 'warehouse' && liveReason && liveReason !== 'ready';
  const liveDatasetMessage = liveReason
    ? messageForLiveDatasetReason(liveReason, liveDetail)
    : null;
  const shouldShowEmptyState =
    creativeAvailability?.status === 'empty' || (!creative.data && creative.status !== 'loading');
  const handleRetry = useCallback(() => {
    void loadAll(tenantId, { force: true });
  }, [loadAll, tenantId]);

  const summaryTiles = useMemo(() => {
    const totalSpend = creativeRows.reduce((sum, row) => sum + row.spend, 0);
    const totalImpressions = creativeRows.reduce((sum, row) => sum + row.impressions, 0);
    const totalClicks = creativeRows.reduce((sum, row) => sum + row.clicks, 0);
    const topCreativeSpend =
      creativeRows.length > 0 ? Math.max(...creativeRows.map((row) => row.spend)) : 0;

    return [
      { label: 'Total spend', value: totalSpend, format: 'currency' as const },
      { label: 'Total impressions', value: totalImpressions, format: 'number' as const },
      { label: 'Total clicks', value: totalClicks, format: 'number' as const },
      { label: 'Top creative spend', value: topCreativeSpend, format: 'currency' as const },
    ];
  }, [creativeRows]);

  const bubbleData = useMemo<BubbleScatterDatum[]>(() => {
    // S2 Insights precedent: shape = triangle when accountId filter is set.
    const shape: BubbleScatterDatum['shape'] = accountId ? 'triangle' : 'circle';
    return creativeRows.map((row) => {
      const ctr = row.impressions > 0 ? row.clicks / row.impressions : 0;
      return {
        id: row.id,
        label: row.name,
        x: row.spend,
        y: ctr,
        z: Math.max(1, row.impressions),
        shape,
        color: platformColor(row.platform),
      };
    });
  }, [accountId, creativeRows]);

  const platformComposition = useMemo(() => {
    const byPlatform = new Map<string, number>();
    for (const row of creativeRows) {
      const slug = (row.platform || 'unknown').toLowerCase();
      byPlatform.set(slug, (byPlatform.get(slug) ?? 0) + row.impressions);
    }
    return Array.from(byPlatform.entries()).map(([platform, value]) => ({
      label: formatPlatformLabel(platform),
      value,
      color: platformColor(platform),
    }));
  }, [creativeRows]);

  const drillRows = useMemo<CreativeDrillRow[]>(
    () =>
      creativeRows.map((row) => {
        const ctr = row.impressions > 0 ? row.clicks / row.impressions : 0;
        const cpm = row.impressions > 0 ? (row.spend / row.impressions) * 1000 : 0;
        return {
          id: row.id,
          name: row.name,
          platform: row.platform,
          platformLabel: formatPlatformLabel(row.platform),
          platformColor: platformColor(row.platform),
          spend: row.spend,
          impressions: row.impressions,
          clicks: row.clicks,
          ctr,
          cpm,
          reach: row.reach ?? 0,
        };
      }),
    [creativeRows],
  );

  if (creative.status === 'loading' && !creative.data) {
    return (
      <DashboardState variant="loading" layout="page" message="Loading creative performance..." />
    );
  }

  if (creative.status === 'error' && !creative.data) {
    if (liveDatasetBlocked) {
      return (
        <div className="dashboard-grid single-panel">
          <section className="panel full-width">
            <DashboardState
              variant="empty"
              icon={<CreativeEmptyIcon />}
              title={titleForLiveDatasetReason(liveReason)}
              message={liveDatasetMessage ?? 'Live warehouse metrics are unavailable.'}
              actionLabel="Refresh data"
              onAction={handleRetry}
              layout="panel"
            />
          </section>
        </div>
      );
    }
    const errorTitle =
      creative.errorKind === 'stale_snapshot'
        ? 'Dashboard data is refreshing'
        : creative.errorKind === 'network'
          ? 'Unable to connect'
          : 'Creative performance';
    return (
      <div className="dashboard-grid single-panel">
        <section className="panel full-width">
          <DashboardState
            variant="error"
            title={errorTitle}
            message={creative.error ?? 'Unable to load creative performance.'}
            actionLabel="Retry load"
            onAction={handleRetry}
            layout="panel"
          />
        </section>
      </div>
    );
  }

  // Preserve the 3-branch creative availability empty-state at lines 122–152.
  if (shouldShowEmptyState) {
    const emptyVariant =
      creativeAvailability?.reason === 'no_matching_filters' ? 'no-results' : 'empty';
    const emptyTitle =
      creativeAvailability?.reason === 'no_matching_filters'
        ? 'No creatives match this view'
        : creativeAvailability?.reason === 'no_recent_data'
          ? 'No recent reportable data'
          : 'No creative insights yet';
    const emptyMessage =
      creativeAvailability?.reason === 'no_matching_filters'
        ? 'No creative rows matched the selected client, date range, or search filters.'
        : creativeAvailability?.reason === 'no_recent_data'
          ? 'The selected Meta account is connected, but Meta returned no recent reportable creative results for this window.'
          : 'Creative performance will appear once ads begin accruing spend.';
    return (
      <div className="dashboard-grid single-panel">
        <section className="panel full-width">
          <DashboardState
            variant={emptyVariant}
            icon={<CreativeEmptyIcon />}
            title={emptyTitle}
            message={emptyMessage}
            actionLabel="Refresh data"
            actionVariant="secondary"
            onAction={handleRetry}
            layout="panel"
          />
        </section>
      </div>
    );
  }

  return (
    <div className="dashboardGrid">
      {/* S4a: KpiTile × 4 strip (Total Spend / Impressions / Clicks / Top creative spend) */}
      <div className="kpiColumn" role="group" aria-label="Creative KPIs">
        {summaryTiles.map((tile) => (
          <KpiTile
            key={tile.label}
            label={tile.label}
            value={tile.value === 0 && tile.format !== 'number' ? null : tile.value}
            format={tile.format}
            currency={currency}
            reasonCode={`creative_${tile.label.toLowerCase().replace(/\s+/g, '_')}`}
          />
        ))}
      </div>

      {/* S4a: Platform color legend (non-color text encoding) */}
      {platformComposition.length > 0 ? (
        <Card title="Platforms" className="chartCard">
          <ul
            aria-label="Creative platform legend"
            style={{
              display: 'flex',
              gap: '1rem',
              listStyle: 'none',
              padding: 0,
              margin: 0,
              flexWrap: 'wrap',
            }}
          >
            {platformComposition.map((item) => (
              <li
                key={item.label}
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

      {/* S4a: BubbleScatter — spend × ctr × impressions, shape encodes accountId filter */}
      <Card title="Creative performance scatter" className="chartCard">
        {creative.status === 'loading' ? (
          <ChartSkeleton height={320} variant="bubble" />
        ) : (
          <BubbleScatter
            data={bubbleData}
            xLabel="Spend"
            yLabel="CTR"
            zLabel="Impressions"
            xFormat="currency"
            yFormat="percent"
            zFormat="number"
            currency={currency}
            ariaLabel="Creative performance scatter"
            emptyReasonCode="no_data_for_range"
            height={320}
          />
        )}
      </Card>

      {/* S4a: PieComposition — impressions split by platform */}
      <Card title="Impressions by platform" className="chartCard">
        {creative.status === 'loading' ? (
          <ChartSkeleton height={260} variant="pie" />
        ) : (
          <PieComposition
            data={platformComposition}
            yFormat="number"
            ariaLabel="Impressions by platform"
            emptyReasonCode="no_data_for_range"
          />
        )}
      </Card>

      {/* S4a: VizDataTable drill-down with platform color chip + CSV export */}
      <Card title="Creative drill-down" className="tableCardWide">
        <VizDataTable
          ariaLabel="Creative drill-down"
          caption="Creative drill-down"
          captionHidden
          csvFilename="creative-drilldown.csv"
          data={drillRows}
          getRowId={(row) => row.id}
          columns={[
            { accessorKey: 'name', header: 'Creative' },
            {
              accessorKey: 'platformLabel',
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
                      background: row.original.platformColor,
                    }}
                  />
                  {row.original.platformLabel}
                </span>
              ),
            },
            {
              accessorKey: 'spend',
              header: 'Spend',
              cell: ({ getValue }) => formatCurrency(Number(getValue()), currency),
            },
            {
              accessorKey: 'impressions',
              header: 'Impressions',
              cell: ({ getValue }) => formatNumber(Number(getValue())),
            },
            {
              accessorKey: 'clicks',
              header: 'Clicks',
              cell: ({ getValue }) => formatNumber(Number(getValue())),
            },
            {
              accessorKey: 'ctr',
              header: 'CTR',
              cell: ({ getValue }) => `${(Number(getValue()) * 100).toFixed(2)}%`,
            },
            {
              accessorKey: 'cpm',
              header: 'CPM',
              cell: ({ getValue }) => formatCurrency(Number(getValue()), currency),
            },
            {
              accessorKey: 'reach',
              header: 'Reach',
              cell: ({ getValue }) => formatNumber(Number(getValue())),
            },
          ]}
        />
      </Card>

      {/* Legacy CreativeTable retained as a compact drill-down companion */}
      <Card title="Creative leaderboard" className="tableCardWide">
        <CreativeTable rows={creativeRows} currency={currency} />
      </Card>
    </div>
  );
};

export default CreativeDashboard;
