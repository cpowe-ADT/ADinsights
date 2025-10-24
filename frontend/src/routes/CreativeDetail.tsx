import { useEffect, useMemo, type ReactNode } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import EmptyState from '../components/EmptyState';
import ErrorState from '../components/ErrorState';
import Skeleton from '../components/Skeleton';
import Card from '../components/ui/Card';
import StatCard from '../components/ui/StatCard';
import { formatCurrency, formatNumber, formatPercent, formatRatio } from '../lib/format';
import useDashboardStore from '../state/useDashboardStore';

const CreativeNotFoundIcon = () => (
  <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="2.2">
    <rect x="10" y="12" width="28" height="20" rx="3" />
    <path d="M18 18h12" strokeLinecap="round" />
    <path d="M18 24h12" strokeLinecap="round" />
    <path d="M24 32v4" strokeLinecap="round" />
    <path d="M20 36h8" strokeLinecap="round" />
  </svg>
);

const CreativeDetail = (): JSX.Element => {
  const navigate = useNavigate();
  const { creativeId: encodedId } = useParams<{ creativeId: string }>();
  const creativeId = useMemo(() => {
    if (!encodedId) {
      return undefined;
    }
    try {
      return decodeURIComponent(encodedId);
    } catch (error) {
      console.warn('Failed to decode creative id segment', error);
      return encodedId;
    }
  }, [encodedId]);

  const { tenantId } = useAuth();
  const { campaign, creative, loadAll } = useDashboardStore((state) => ({
    campaign: state.campaign,
    creative: state.creative,
    loadAll: state.loadAll,
  }));

  const creatives = creative.data ?? [];
  const activeCreative = useMemo(
    () => creatives.find((row) => row.id === creativeId),
    [creatives, creativeId],
  );

  const campaignRows = campaign.data?.rows ?? [];
  const parentCampaign = useMemo(
    () => campaignRows.find((row) => row.id === activeCreative?.campaignId),
    [campaignRows, activeCreative?.campaignId],
  );

  const currency = campaign.data?.summary.currency ?? 'USD';

  useEffect(() => {
    const hasCreativeRows = creatives.length > 0;
    if (!hasCreativeRows && creative.status === 'idle') {
      void loadAll(tenantId);
    }
  }, [creative.status, creatives.length, loadAll, tenantId]);

  const isLoading = creative.status === 'loading' && !activeCreative;
  const showError = creative.status === 'error' && !activeCreative;

  const kpis = activeCreative
    ? [
        { label: 'Spend', value: formatCurrency(activeCreative.spend, currency) },
        { label: 'Impressions', value: formatNumber(activeCreative.impressions) },
        { label: 'Clicks', value: formatNumber(activeCreative.clicks) },
        { label: 'Conversions', value: formatNumber(activeCreative.conversions) },
        { label: 'ROAS', value: formatRatio(activeCreative.roas, 2) },
      ]
    : [];

  type OverviewItem = { label: string; value: ReactNode };
  const overviewItems: OverviewItem[] = activeCreative
    ? [
        {
          label: 'Campaign',
          value: parentCampaign ? (
            <Link className="table-link" to={`/dashboards/campaigns/${encodeURIComponent(parentCampaign.id)}`}>
              {parentCampaign.name}
            </Link>
          ) : (
            activeCreative.campaignName
          ),
        },
        { label: 'Platform', value: activeCreative.platform ?? '—' },
        { label: 'Primary parish', value: activeCreative.parish ?? '—' },
        {
          label: 'CTR',
          value:
            typeof activeCreative.ctr === 'number' ? formatPercent(activeCreative.ctr, 2) : '—',
        },
        { label: 'ROAS', value: formatRatio(activeCreative.roas, 2) },
      ]
    : [];

  const pageShell = (content: ReactNode) => (
    <section className="dashboardPage" aria-labelledby="creative-detail-heading">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Creative detail</p>
        <h1 className="dashboardHeading" id="creative-detail-heading">
          {activeCreative ? activeCreative.name : 'Creative insights'}
        </h1>
        <Link to="/dashboards/creatives" className="backLink">
          ← Back to creatives
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
        <Card title="Creative overview">
          <Skeleton height={200} borderRadius="0.75rem" />
        </Card>
      </div>,
    );
  }

  if (showError) {
    return pageShell(
      <div className="dashboardGrid">
        <Card title="Creative overview">
          <ErrorState
            message={creative.error ?? 'Unable to load creative details.'}
            retryLabel="Retry"
            onRetry={() => {
              void loadAll(tenantId, { force: true });
            }}
          />
        </Card>
      </div>,
    );
  }

  if (!activeCreative) {
    return pageShell(
      <div className="dashboardGrid">
        <Card title="Creative overview">
          <EmptyState
            icon={<CreativeNotFoundIcon />}
            title="Creative not found"
            message="This creative could not be located."
            actionLabel="Return to creatives"
            onAction={() => {
              navigate('/dashboards/creatives');
            }}
          />
        </Card>
      </div>,
    );
  }

  return pageShell(
    <div className="dashboardGrid">
      <div className="kpiColumn" role="group" aria-label="Creative KPIs">
        {kpis.map((kpi) => (
          <StatCard key={kpi.label} label={kpi.label} value={kpi.value} />
        ))}
      </div>
      <Card title="Creative overview">
        <div className="creativeDetail">
          {activeCreative.thumbnailUrl ? (
            <img
              src={activeCreative.thumbnailUrl}
              alt={activeCreative.name}
              className="creativeDetailPreview"
              loading="lazy"
            />
          ) : (
            <div className="creativeDetailFallback" aria-hidden="true">
              {activeCreative.name.slice(0, 2).toUpperCase()}
            </div>
          )}
          <dl className="detailGrid">
            {overviewItems.map((item) => (
              <div key={item.label}>
                <dt>{item.label}</dt>
                <dd>{item.value}</dd>
              </div>
            ))}
          </dl>
        </div>
      </Card>
    </div>,
  );
};

export default CreativeDetail;
