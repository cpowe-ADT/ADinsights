import { useState } from 'react';

import GoogleAdsDataTablePage from '../../components/google-ads/GoogleAdsDataTablePage';

const GoogleAdsKeywordsPage = () => {
  const [mode, setMode] = useState<'keywords' | 'search_terms' | 'insights'>('keywords');

  const endpoint =
    mode === 'keywords'
      ? '/analytics/google-ads/keywords/'
      : mode === 'search_terms'
        ? '/analytics/google-ads/search-terms/'
        : '/analytics/google-ads/search-term-insights/';

  return (
    <div>
      <div className="panel" style={{ marginBottom: '1rem' }}>
        <div className="dashboard-header__actions-row">
          <button className="button secondary" type="button" onClick={() => setMode('keywords')}>
            Keywords
          </button>
          <button className="button secondary" type="button" onClick={() => setMode('search_terms')}>
            Search Terms
          </button>
          <button className="button secondary" type="button" onClick={() => setMode('insights')}>
            Insights
          </button>
        </div>
      </div>
      <GoogleAdsDataTablePage
        eyebrow="Google Ads"
        title="Keywords & Search Terms"
        description="Keyword performance, search terms, and grouped search-term insights."
        endpoint={endpoint}
      />
    </div>
  );
};

export default GoogleAdsKeywordsPage;
