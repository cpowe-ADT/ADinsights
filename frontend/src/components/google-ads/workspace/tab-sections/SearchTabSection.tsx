import { useMemo } from 'react';

import {
  BubbleScatter,
  DistributionBar,
  EmptyState,
  KpiTile,
} from '../../../viz';
import {
  buildQsCpcBubblePoints,
  rollupKeywordKpis,
  topSearchTermsByConv,
  type GoogleAdsKeywordRow,
  type GoogleAdsSearchTermRow,
} from '../../../../lib/googleAdsAggregates';
import type { SearchMode } from '../types';

type Payload = {
  count?: number;
  results?: Array<Record<string, unknown>>;
};

type Props = {
  searchMode: SearchMode;
  data: unknown;
  status: 'idle' | 'loading' | 'success' | 'error';
  error: string;
  /**
   * Architect §6.3: the Top-10 search-terms bar is rendered on the
   * keywords view as a secondary chart. The workspace page prefetches
   * the `search_terms` mode once and passes the results through here.
   * When undefined/null the chart slot renders an EmptyState.
   */
  searchTermRows?: GoogleAdsSearchTermRow[] | null;
};

const EmptyIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
    <circle cx="11" cy="11" r="7" />
    <path d="M21 21l-4.3-4.3" />
  </svg>
);

const reasonCodeFor = (mode: SearchMode): string => {
  if (mode === 'search_terms') return 'no_search_terms';
  if (mode === 'insights') return 'no_search_insights';
  return 'no_keywords';
};

const SearchTabSection = ({ searchMode, data, status, error, searchTermRows }: Props) => {
  const payload = (data as Payload) ?? {};
  const rows = useMemo(
    () => (Array.isArray(payload.results) ? payload.results : []),
    [payload.results],
  );

  const keywordRows = useMemo<GoogleAdsKeywordRow[]>(
    () => rows as GoogleAdsKeywordRow[],
    [rows],
  );
  const kpis = useMemo(() => rollupKeywordKpis(keywordRows), [keywordRows]);
  const bubbles = useMemo(
    () => (searchMode === 'keywords' ? buildQsCpcBubblePoints(keywordRows) : []),
    [searchMode, keywordRows],
  );
  const topTerms = useMemo(
    () => topSearchTermsByConv(searchTermRows),
    [searchTermRows],
  );

  if (status === 'loading' && rows.length === 0) {
    return <div className="panel">Loading search data...</div>;
  }
  if (status === 'error' && rows.length === 0) {
    return (
      <div className="panel" role="alert">
        {error}
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <EmptyState
        icon={<EmptyIcon />}
        title="No data for this mode"
        message="Adjust filters or try a different search mode."
        reasonCode={reasonCodeFor(searchMode)}
      />
    );
  }

  const columns =
    searchMode === 'keywords'
      ? [
          { key: 'keyword_text', label: 'Keyword' },
          { key: 'match_type', label: 'Match Type' },
          { key: 'keyword_status', label: 'Status' },
          { key: 'quality_score', label: 'QS' },
          { key: 'impressions', label: 'Impressions' },
          { key: 'clicks', label: 'Clicks' },
          { key: 'conversions', label: 'Conv' },
          { key: 'cpa', label: 'CPA' },
        ]
      : searchMode === 'search_terms'
        ? [
            { key: 'search_term', label: 'Search Term' },
            { key: 'impressions', label: 'Impressions' },
            { key: 'clicks', label: 'Clicks' },
            { key: 'conversions', label: 'Conv' },
            { key: 'cpa', label: 'CPA' },
          ]
        : Object.keys(rows[0] ?? {}).map((key) => ({ key, label: key.replace(/_/g, ' ') }));

  return (
    <div
      className="gads-workspace__tab-grid"
      data-testid="google-ads-search-section"
    >
      <section className="panel">
        <h2>Search KPIs</h2>
        <div
          className="gads-workspace__kpi-grid"
          role="list"
          aria-label="Google Ads search KPIs"
        >
          <KpiTile
            label={searchMode === 'keywords' ? 'Total Keywords' : 'Total Rows'}
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
      </section>

      {searchMode === 'keywords' ? (
        <section className="panel">
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
        </section>
      ) : null}

      <section className="panel">
        <h2>Top 10 search terms by conversions</h2>
        {topTerms.length === 0 ? (
          <EmptyState
            icon={<EmptyIcon />}
            title="Search terms unavailable"
            message="Switch to the Search Terms mode to load this chart."
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
      </section>

      <section className="panel">
        <h2>Results ({payload.count ?? rows.length})</h2>
        <div className="table-responsive">
          <table className="dashboard-table">
            <thead>
              <tr className="dashboard-table__header-row">
                {columns.map((col) => (
                  <th key={col.key} className="dashboard-table__header-cell">
                    {col.label}
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
                  {columns.map((col) => (
                    <td key={col.key} className="dashboard-table__cell">
                      {row[col.key] === null || row[col.key] === undefined
                        ? '—'
                        : String(row[col.key])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
};

export default SearchTabSection;
