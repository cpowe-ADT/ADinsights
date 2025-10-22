import { useCallback } from 'react';
import { ResponsiveContainer } from 'recharts';

import CampaignTable from '../components/CampaignTable';
import CampaignTrendChart from '../components/CampaignTrendChart';
import EmptyState from '../components/EmptyState';
import ErrorState from '../components/ErrorState';
import ParishMap from '../components/ParishMap';
import Skeleton from '../components/Skeleton';
import Card from '../components/ui/Card';
import StatCard from '../components/ui/StatCard';
import { useAuth } from '../auth/AuthContext';
import useDashboardStore from '../state/useDashboardStore';
import { formatCurrency, formatNumber, formatRatio } from '../lib/format';

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
  const { campaign, campaignRows, loadAll } = useDashboardStore((state) => ({
    campaign: state.campaign,
    campaignRows: state.getCampaignRowsForSelectedParish(),
    loadAll: state.loadAll,
  }));

  const isInitialLoading = campaign.status === 'loading' && !campaign.data;
  const hasCampaignData = Boolean(campaign.data);

  const handleRetry = useCallback(() => {
    void loadAll(tenantId, { force: true });
  }, [loadAll, tenantId]);

  if (campaign.status === 'error' && !hasCampaignData) {
    return (
      <div>
        <h1 className="dashboardHeading" aria-label="Campaign dashboard">
          Campaign performance
        </h1>
        <div className="dashboardGrid">
          <Card title="Campaign insights" className="chartCard">
            <div className="status-message">
              <ErrorState
                message={campaign.error ?? 'Unable to load campaign performance.'}
                onRetry={handleRetry}
                retryLabel="Retry load"
              />
            </div>
          </Card>
        </div>
      </div>
    );
  }

  if (!hasCampaignData && !isInitialLoading) {
    return (
      <div>
        <h1 className="dashboardHeading" aria-label="Campaign dashboard">
          Campaign performance
        </h1>
        <div className="dashboardGrid">
          <Card title="Campaign insights" className="chartCard">
            <EmptyState
              icon={<CampaignEmptyIcon />}
              title="No campaign insights yet"
              message="Campaign performance will appear once metrics are ingested."
              actionLabel="Refresh data"
              onAction={handleRetry}
            />
          </Card>
        </div>
      </div>
    );
  }

  const summary = campaign.data?.summary;
  const trend = campaign.data?.trend ?? [];
  const currency = summary?.currency ?? 'USD';

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

  const hasTrendData = trend.length > 0;
  const kpis = [
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
  ];

  const dateRangeFormatter = new Intl.DateTimeFormat('en-JM', { month: 'short', day: 'numeric' });

  const chartFooter = hasTrendData ? (
    <div className="chartFooter">
      <div>
        <span>Peak daily spend</span>
        <strong>{formatCurrency(Math.max(...trend.map((point) => point.spend)), currency)}</strong>
      </div>
      <div className="chartFooterDates">
        <span>{dateRangeFormatter.format(new Date(trend[0].date))}</span>
        <span aria-hidden="true">–</span>
        <span>{dateRangeFormatter.format(new Date(trend[trend.length - 1].date))}</span>
      </div>
    </div>
  ) : null;

  return (
    <div>
      <h1 className="dashboardHeading" aria-label="Campaign dashboard">
        Campaign performance
      </h1>
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
              <CampaignTrendChart data={trend} currency={currency} />
            </ResponsiveContainer>
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
          {chartFooter}
        </Card>

        <Card className="mapCard" title="Parish heatmap">
          <p className="muted">Click a parish to filter the performance tables below.</p>
          <div className="mapViewport">
            <ParishMap onRetry={handleRetry} />
          </div>
        </Card>

        <Card title="Campaign metrics table">
          <CampaignTable
            rows={campaignRows}
            currency={currency}
            isLoading={campaign.status === 'loading'}
            onReload={handleRetry}
          />
        </Card>
      </div>
    </div>
  );
};

export default CampaignDashboard;
