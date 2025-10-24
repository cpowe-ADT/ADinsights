import { useEffect, useMemo, type ReactNode } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import CreativeTable from '../components/CreativeTable';
import EmptyState from '../components/EmptyState';
import ErrorState from '../components/ErrorState';
import Skeleton from '../components/Skeleton';
import Card from '../components/ui/Card';
import StatCard from '../components/ui/StatCard';
import { formatCurrency, formatNumber, formatPercent, formatRatio } from '../lib/format';
import useDashboardStore from '../state/useDashboardStore';

const formatDate = (value?: string): string => {
  if (!value) {
    return '—';
  }
  try {
    return new Intl.DateTimeFormat('en-JM', { dateStyle: 'medium' }).format(new Date(value));
  } catch (error) {
    console.warn('Failed to format date', error);
    return value;
  }
};

const CampaignNotFoundIcon = () => (
  <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="2.2">
    <rect x="8" y="12" width="32" height="24" rx="4" />
    <path d="M12 18h24M12 24h24M12 30h18" strokeLinecap="round" />
    <path d="m32 30 6 6" strokeLinecap="round" />
    <circle cx="32" cy="30" r="4" />
  </svg>
);

const CreativesEmptyIcon = () => (
  <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="2.2">
    <rect x="10" y="12" width="12" height="16" rx="2.5" />
    <rect x="26" y="12" width="12" height="16" rx="2.5" />
    <path d="M12 34h24" strokeLinecap="round" />
  </svg>
);

type OverviewItem = { label: string; value: ReactNode };

const CampaignDetail = (): JSX.Element => {
  const navigate = useNavigate();
  const { campaignId: encodedId } = useParams<{ campaignId: string }>();
  const campaignId = useMemo(() => {
    if (!encodedId) {
      return undefined;
    }
    try {
      return decodeURIComponent(encodedId);
    } catch (error) {
      console.warn('Failed to decode campaign id segment', error);
      return encodedId;
    }
  }, [encodedId]);

  const { tenantId } = useAuth();
  const { campaign, creative, loadAll } = useDashboardStore((state) => ({
    campaign: state.campaign,
    creative: state.creative,
    loadAll: state.loadAll,
  }));

  const campaignRows = campaign.data?.rows ?? [];
  const activeCampaign = useMemo(
    () => campaignRows.find((row) => row.id === campaignId),
    [campaignRows, campaignId],
  );

  const currency = campaign.data?.summary.currency ?? 'USD';
  const relatedCreatives = useMemo(() => {
    if (!campaignId) {
      return [];
    }
    return (creative.data ?? []).filter((row) => row.campaignId === campaignId);
  }, [campaignId, creative.data]);

  useEffect(() => {
    const hasLoadedRows = campaignRows.length > 0;
    if (!hasLoadedRows && campaign.status === 'idle') {
      void loadAll(tenantId);
    }
  }, [campaign.status, campaignRows.length, loadAll, tenantId]);

  const isLoading = campaign.status === 'loading' && !activeCampaign;
  const showError = campaign.status === 'error' && !activeCampaign;

  const kpis = activeCampaign
    ? [
        { label: 'Spend', value: formatCurrency(activeCampaign.spend, currency) },
        { label: 'Impressions', value: formatNumber(activeCampaign.impressions) },
        { label: 'Clicks', value: formatNumber(activeCampaign.clicks) },
        { label: 'Conversions', value: formatNumber(activeCampaign.conversions) },
        { label: 'ROAS', value: formatRatio(activeCampaign.roas, 2) },
      ]
    : [];

  const overviewItems: OverviewItem[] = activeCampaign
    ? [
        { label: 'Status', value: activeCampaign.status ?? '—' },
        { label: 'Platform', value: activeCampaign.platform ?? '—' },
        { label: 'Objective', value: activeCampaign.objective ?? '—' },
        { label: 'Primary parish', value: activeCampaign.parish ?? '—' },
        { label: 'CTR', value: typeof activeCampaign.ctr === 'number' ? formatPercent(activeCampaign.ctr, 2) : '—' },
        { label: 'CPC', value: typeof activeCampaign.cpc === 'number' ? formatCurrency(activeCampaign.cpc, currency, 2) : '—' },
        { label: 'CPM', value: typeof activeCampaign.cpm === 'number' ? formatCurrency(activeCampaign.cpm, currency, 2) : '—' },
        { label: 'Start date', value: formatDate(activeCampaign.startDate) },
        { label: 'End date', value: formatDate(activeCampaign.endDate) },
      ]
    : [];

  const pageShell = (content: ReactNode) => (
    <section className="dashboardPage" aria-labelledby="campaign-detail-heading">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Campaign detail</p>
        <h1 className="dashboardHeading" id="campaign-detail-heading">
          {activeCampaign ? activeCampaign.name : 'Campaign insights'}
        </h1>
        <Link to="/dashboards/campaigns" className="backLink">
          ← Back to campaigns
        </Link>
      </header>
      {content}
    </section>
  );

  if (isLoading) {
    return pageShell(
      <div className="dashboardGrid">
        <div className="kpiColumn">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} height={120} borderRadius="1rem" />
          ))}
        </div>
        <Card title="Campaign overview">
          <Skeleton height={180} borderRadius="0.75rem" />
        </Card>
      </div>,
    );
  }

  if (showError) {
    return pageShell(
      <div className="dashboardGrid">
        <Card title="Campaign overview">
          <ErrorState
            message={campaign.error ?? 'Unable to load campaign details.'}
            retryLabel="Retry"
            onRetry={() => {
              void loadAll(tenantId, { force: true });
            }}
          />
        </Card>
      </div>,
    );
  }

  if (!activeCampaign) {
    return pageShell(
      <div className="dashboardGrid">
        <Card title="Campaign overview">
          <EmptyState
            icon={<CampaignNotFoundIcon />}
            title="Campaign not found"
            message="This campaign is no longer available."
            actionLabel="Return to campaigns"
            onAction={() => {
              navigate('/dashboards/campaigns');
            }}
          />
        </Card>
      </div>,
    );
  }

  return pageShell(
    <div className="dashboardGrid">
      <div className="kpiColumn" role="group" aria-label="Campaign KPIs">
        {kpis.map((kpi) => (
          <StatCard key={kpi.label} label={kpi.label} value={kpi.value} />
        ))}
      </div>
      <Card title="Campaign overview">
        <dl className="detailGrid">
          {overviewItems.map((item) => (
            <div key={item.label}>
              <dt>{item.label}</dt>
              <dd>{item.value}</dd>
            </div>
          ))}
        </dl>
      </Card>
      {relatedCreatives.length > 0 ? (
        <CreativeTable rows={relatedCreatives} currency={currency} />
      ) : (
        <Card title="Related creatives">
          <EmptyState
            icon={<CreativesEmptyIcon />}
            title="No creatives linked"
            message="Creatives associated with this campaign will appear here once available."
            actionLabel="Refresh data"
            actionVariant="secondary"
            onAction={() => {
              void loadAll(tenantId, { force: true });
            }}
          />
        </Card>
      )}
    </div>,
  );
};

export default CampaignDetail;
