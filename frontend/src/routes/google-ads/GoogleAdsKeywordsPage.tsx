import { useEffect, useMemo, useState } from 'react';

import {
  BubbleScatter,
  DistributionBar,
  EmptyState,
  KpiTile,
} from '../../components/viz';
import {
  buildQsCpcBubblePoints,
  rollupKeywordKpis,
  topSearchTermsByConv,
  type GoogleAdsKeywordRow,
  type GoogleAdsSearchTermRow,
} from '../../lib/googleAdsAggregates';
import {
  fetchGoogleAdsList,
  type GoogleAdsListResponse,
} from '../../lib/googleAdsDashboard';
import { appendQueryParams } from '../../lib/apiClient';
import { resolveFilterRange } from '../../lib/dashboardFilters';
import useDashboardStore from '../../state/useDashboardStore';

type Mode = 'keywords' | 'search_terms' | 'insights';

const EmptyIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
    <circle cx="11" cy="11" r="7" />
    <path d="M21 21l-4.3-4.3" />
  </svg>
);

const endpointFor = (mode: Mode): string => {
  if (mode === 'search_terms') return '/analytics/google-ads/search-terms/';
  if (mode === 'insights') return '/analytics/google-ads/search-term-insights/';
  return '/analytics/google-ads/keywords/';
};

const reasonCodeFor = (mode: Mode): string => {
  if (mode === 'search_terms') return 'no_search_terms';
  if (mode === 'insights') return 'no_search_insights';
  return 'no_keywords';
};

/**
 * Sprint 3 — legacy Keywords page. Replaces the GoogleAdsDataTablePage
 * wrapper with the shared viz kit per architect §6.3. Supports the three
 * modes (keywords / search_terms / insights); when mode=keywords we also
 * prefetch search_terms once for the top-10 bar.
 */
const GoogleAdsKeywordsPage = () => {
  const [mode, setMode] = useState<Mode>('keywords');
  const [payload, setPayload] = useState<GoogleAdsListResponse<Record<string, unknown>>>({
    count: 0,
    results: [],
  });
  const [searchTermPayload, setSearchTermPayload] = useState<GoogleAdsSearchTermRow[]>([]);
  const [status, setStatus] = useState<'idle' | 'loading' | 'error'>('loading');
  const [error, setError] = useState('');
  const filters = useDashboardStore((state) => state.filters);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setStatus('loading');
      setError('');
      try {
        const { start, end } = resolveFilterRange(filters);
        const path = appendQueryParams(endpointFor(mode), {
          platforms: 'google_ads',
          customer_id: filters.accountId || undefined,
          start_date: start || undefined,
          end_date: end || undefined,
        });
        const response = await fetchGoogleAdsList<Record<string, unknown>>(path);
        if (!active) return;
        setPayload(response);
        setStatus('idle');
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : 'Failed to load search data.');
        setStatus('error');
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, [filters, mode]);

  // Secondary prefetch: top-10 search-terms bar on the keywords view.
  useEffect(() => {
    if (mode !== 'keywords') return;
    let active = true;
    const loadTerms = async () => {
      try {
        const { start, end } = resolveFilterRange(filters);
        const path = appendQueryParams('/analytics/google-ads/search-terms/', {
          platforms: 'google_ads',
          customer_id: filters.accountId || undefined,
          start_date: start || undefined,
          end_date: end || undefined,
        });
        const response = await fetchGoogleAdsList<GoogleAdsSearchTermRow>(path);
        if (!active) return;
        setSearchTermPayload(response.results ?? []);
      } catch {
        if (!active) return;
        setSearchTermPayload([]);
      }
    };
    void loadTerms();
    return () => {
      active = false;
    };
  }, [filters, mode]);

  const rows = payload.results;
  const keywordRows = rows as GoogleAdsKeywordRow[];
  const kpis = useMemo(() => rollupKeywordKpis(keywordRows), [keywordRows]);
  const bubbles = useMemo(
    () => (mode === 'keywords' ? buildQsCpcBubblePoints(keywordRows) : []),
    [mode, keywordRows],
  );
  const topTerms = useMemo(() => topSearchTermsByConv(searchTermPayload), [searchTermPayload]);

  return (
    <section className="dashboardPage">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Google Ads</p>
        <h1 className="dashboardHeading">Keywords &amp; Search Terms</h1>
        <p className="dashboardSubtitle">
          Keyword performance, search terms, and grouped search-term insights.
        </p>
      </header>

      <div className="panel" style={{ marginBottom: '1rem' }}>
        <div className="dashboard-header__actions-row" role="group" aria-label="Search data mode">
          <button
            type="button"
            className={`button secondary${mode === 'keywords' ? ' is-active' : ''}`}
            onClick={() => setMode('keywords')}
          >
            Keywords
          </button>
          <button
            type="button"
            className={`button secondary${mode === 'search_terms' ? ' is-active' : ''}`}
            onClick={() => setMode('search_terms')}
          >
            Search Terms
          </button>
          <button
            type="button"
            className={`button secondary${mode === 'insights' ? ' is-active' : ''}`}
            onClick={() => setMode('insights')}
          >
            Insights
          </button>
        </div>
      </div>

      {status === 'loading' ? (
        <div className="dashboard-state dashboard-state--page">Loading search data...</div>
      ) : null}
      {status === 'error' ? (
        <div className="dashboard-state dashboard-state--page" role="alert">
          {error}
        </div>
      ) : null}

      {status !== 'loading' && rows.length === 0 ? (
        <EmptyState
          icon={<EmptyIcon />}
          title="No data for this mode"
          message="Adjust filters or try a different search mode."
          reasonCode={reasonCodeFor(mode)}
        />
      ) : null}

      {rows.length > 0 ? (
        <>
          <div className="panel" style={{ marginBottom: '1rem' }}>
            <h2>Search KPIs</h2>
            <div
              className="gads-workspace__kpi-grid"
              role="list"
              aria-label="Google Ads search KPIs"
            >
              <KpiTile
                label={mode === 'keywords' ? 'Total Keywords' : 'Total Rows'}
                value={kpis.count}
                format="number"
              />
              <KpiTile
                label="Avg Quality Score"
                value={kpis.avgQualityScore}
                format="number"
                reasonCode={kpis.avgQualityScore === null ? 'no_data_for_range' : undefined}
              />
              <KpiTile label="Top Row Conversions" value={kpis.topConversions} format="number" />
            </div>
          </div>

          {mode === 'keywords' ? (
            <div className="panel" style={{ marginBottom: '1rem' }}>
              <h2>Quality Score vs. CPC</h2>
              <BubbleScatter
                data={bubbles}
                xLabel="Quality Score"
                yLabel="CPC"
                zLabel="Impressions"
                xFormat="number"
                yFormat="currency"
                zFormat="number"
                currency="JMD"
                ariaLabel="Keyword quality score vs CPC bubble scatter"
                emptyReasonCode="no_keywords"
              />
            </div>
          ) : null}

          {mode === 'keywords' ? (
            <div className="panel" style={{ marginBottom: '1rem' }}>
              <h2>Top 10 search terms by conversions</h2>
              {topTerms.length === 0 ? (
                <EmptyState
                  icon={<EmptyIcon />}
                  title="Search terms unavailable"
                  message="Search-terms data could not be loaded."
                  reasonCode="no_search_terms"
                />
              ) : (
                <DistributionBar
                  data={topTerms}
                  yFormat="number"
                  ariaLabel="Top search terms by conversions"
                  emptyReasonCode="no_search_terms"
                />
              )}
            </div>
          ) : null}

          <div className="panel">
            <h2>Results ({payload.count ?? rows.length})</h2>
            <div className="table-responsive">
              <table className="dashboard-table">
                <thead>
                  <tr className="dashboard-table__header-row">
                    {Object.keys(rows[0] ?? {}).map((column) => (
                      <th key={column} className="dashboard-table__header-cell">
                        {column.replace(/_/g, ' ')}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, idx) => (
                    <tr
                      key={idx}
                      className="dashboard-table__row dashboard-table__row--zebra"
                    >
                      {Object.keys(rows[0] ?? {}).map((column) => (
                        <td key={column} className="dashboard-table__cell">
                          {row[column] === null || row[column] === undefined
                            ? '—'
                            : String(row[column])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
};

export default GoogleAdsKeywordsPage;
