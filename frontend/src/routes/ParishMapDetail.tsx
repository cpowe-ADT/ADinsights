import { useCallback, useId, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';

import Card from '../components/ui/Card';
import StatCard from '../components/ui/StatCard';
import ParishMap from '../components/ParishMap';
import ParishDetailPanel from '../components/ParishDetailPanel';
import ParishComparisonChart from '../components/ParishComparisonChart';
import RegionBreakdownTable from '../components/RegionBreakdownTable';
import DashboardState from '../components/DashboardState';
import Skeleton from '../components/Skeleton';
import { useAuth } from '../auth/AuthContext';
import useDashboardStore, { normalizeParishValue } from '../state/useDashboardStore';
import { formatCurrency, formatNumber, formatRatio } from '../lib/format';

import '../styles/dashboard.css';

const safeDiv = (num: number, den: number) => (den > 0 ? num / den : 0);


const ParishMapDetail = () => {
  const navigate = useNavigate();
  const { tenantId } = useAuth();
  const headingId = useId();

  const {
    parish,
    selectedParish,
    setSelectedParish,
    selectedMetric,
    campaignSummary,
    loadAll,
  } = useDashboardStore((state) => ({
    parish: state.parish,
    selectedParish: state.selectedParish,
    setSelectedParish: state.setSelectedParish,
    selectedMetric: state.selectedMetric,
    campaignSummary: state.campaign.data?.summary,
    loadAll: state.loadAll,
  }));

  const parishRows = useMemo(() => parish.data ?? [], [parish.data]);
  const currency = campaignSummary?.currency ?? parishRows[0]?.currency ?? 'USD';

  const islandTotals = useMemo(() => {
    const totals = parishRows.reduce(
      (acc, row) => ({
        spend: acc.spend + row.spend,
        impressions: acc.impressions + row.impressions,
        clicks: acc.clicks + row.clicks,
        conversions: acc.conversions + row.conversions,
      }),
      { spend: 0, impressions: 0, clicks: 0, conversions: 0 },
    );
    return { ...totals, roas: safeDiv(totals.conversions, totals.spend) };
  }, [parishRows]);

  const selectedParishData = useMemo(
    () => {
      if (!selectedParish) return undefined;
      const key = normalizeParishValue(selectedParish);
      return parishRows.find((r) => normalizeParishValue(r.parish) === key);
    },
    [parishRows, selectedParish],
  );

  const displayData = selectedParishData ?? islandTotals;
  const displayLabel = selectedParish ?? 'All Jamaica';

  const handleBack = useCallback(() => {
    if (window.history.length > 1) {
      navigate(-1);
      return;
    }
    navigate('/dashboards/campaigns');
  }, [navigate]);

  const handleRetry = useCallback(() => {
    void loadAll(tenantId, { force: true });
  }, [loadAll, tenantId]);

  const clearSelection = useCallback(() => {
    setSelectedParish(undefined);
  }, [setSelectedParish]);

  const kpis = useMemo(
    () => [
      { label: 'Spend', value: formatCurrency(displayData.spend, currency) },
      { label: 'Impressions', value: formatNumber(displayData.impressions) },
      { label: 'Clicks', value: formatNumber(displayData.clicks) },
      { label: 'Conversions', value: formatNumber(displayData.conversions) },
      { label: 'ROAS', value: formatRatio(displayData.roas ?? 0, 2) },
    ],
    [displayData, currency],
  );

  const isLoading = parish.status === 'loading' && parishRows.length === 0;

  if (parish.status === 'error' && parishRows.length === 0) {
    return (
      <section className="dashboardPage" aria-labelledby={headingId}>
        <header className="dashboardPageHeader">
          <h1 className="dashboardHeading" id={headingId}>Regional performance</h1>
        </header>
        <DashboardState
          variant="error"
          message={parish.error ?? 'Unable to load parish data.'}
          actionLabel="Retry"
          onAction={handleRetry}
        />
      </section>
    );
  }

  return (
    <section className="dashboardPage" aria-labelledby={headingId}>
      <header className="dashboardPageHeader">
        <h1 className="dashboardHeading" id={headingId}>
          Regional performance
          {selectedParish && (
            <span className="dashboardHeading__sub"> — {selectedParish}</span>
          )}
        </h1>
        <div>
          <button type="button" className="button tertiary" onClick={handleBack}>
            ← Back to dashboard
          </button>
        </div>
      </header>

      <div className="dashboardGrid">
        {/* KPI row */}
        <div className="parishKpiRow" role="group" aria-label={`${displayLabel} KPIs`}>
          {isLoading
            ? Array.from({ length: 5 }, (_, i) => (
                <div key={i} className="widget-skeleton" aria-busy="true">
                  <Skeleton height={100} borderRadius="1rem" />
                </div>
              ))
            : kpis.map((kpi) => (
                <StatCard key={kpi.label} label={kpi.label} value={kpi.value} />
              ))}
        </div>

        {/* Map + detail panel */}
        <div className="parishMapRow">
          <Card className="mapCard" title="Parish heatmap">
            <p className="muted">
              Click a parish to filter. Currently showing: <strong>{displayLabel}</strong>
            </p>
            <div className="mapViewport">
              <ParishMap height={480} onRetry={handleRetry} />
            </div>
          </Card>

          <Card
            title={selectedParish ? `${selectedParish} details` : 'Parish details'}
            className={selectedParish ? 'parishDetailCard--selected' : undefined}
          >
            <ParishDetailPanel
              parish={selectedParishData}
              currency={currency}
              onClear={clearSelection}
            />
          </Card>
        </div>

        {/* Analysis section */}
        {(parishRows.length > 0 || parish.status === 'loading') && (
          <div className="parishAnalysisSection">
            <h2 className="parishSectionLabel">Analysis</h2>
            <div className="parishAnalysisGrid">
              {parishRows.length > 0 && (
                <Card title="Parish comparison" className="tableCardWide">
                  <p className="muted">
                    All parishes ranked by {selectedMetric ?? 'spend'}.
                    {selectedParish ? ` ${selectedParish} is highlighted.` : ''}
                  </p>
                  <ParishComparisonChart
                    data={parishRows}
                    metric={selectedMetric ?? 'spend'}
                    currency={currency}
                    selectedParish={selectedParish}
                  />
                </Card>
              )}
              <Card title="Region breakdown" className="tableCardWide">
                <RegionBreakdownTable onReload={handleRetry} />
              </Card>
            </div>
          </div>
        )}
      </div>
    </section>
  );
};

export default ParishMapDetail;
