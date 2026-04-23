import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import SearchTabSection from '../tab-sections/SearchTabSection';
import type {
  GoogleAdsKeywordRow,
  GoogleAdsSearchTermRow,
} from '../../../../lib/googleAdsAggregates';

const keywordRow = (
  over: Partial<GoogleAdsKeywordRow> = {},
): GoogleAdsKeywordRow => ({
  keyword_text: 'running shoes',
  match_type: 'BROAD',
  keyword_status: 'ENABLED',
  quality_score: 7,
  impressions: 1200,
  clicks: 80,
  conversions: 5,
  cpa: 25,
  ...over,
});

const searchTermRow = (
  over: Partial<GoogleAdsSearchTermRow> = {},
): GoogleAdsSearchTermRow => ({
  search_term: 'best running shoes',
  impressions: 200,
  clicks: 10,
  conversions: 2,
  ...over,
});

describe('SearchTabSection — integration', () => {
  it('renders loading state', () => {
    render(
      <SearchTabSection
        searchMode="keywords"
        data={null}
        status="loading"
        error=""
      />,
    );
    expect(screen.getByText('Loading search data...')).toBeInTheDocument();
  });

  it('renders empty state', () => {
    render(
      <SearchTabSection
        searchMode="keywords"
        data={{ count: 0, results: [] }}
        status="success"
        error=""
      />,
    );
    expect(screen.getByText('No data for this mode')).toBeInTheDocument();
  });

  it('renders populated state', () => {
    const payload = {
      count: 1,
      results: [keywordRow()],
    };
    render(
      <SearchTabSection
        searchMode="keywords"
        data={payload}
        status="success"
        error=""
        searchTermRows={[searchTermRow()]}
      />,
    );
    expect(
      screen.getByTestId('google-ads-search-section'),
    ).toBeInTheDocument();
    expect(screen.getAllByText('running shoes').length).toBeGreaterThan(0);
    expect(screen.getByText('Quality Score vs. CPC')).toBeInTheDocument();
  });
});
