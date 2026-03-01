import GoogleAdsDataTablePage from '../../components/google-ads/GoogleAdsDataTablePage';

const GoogleAdsRecommendationsPage = () => (
  <GoogleAdsDataTablePage
    eyebrow="Google Ads"
    title="Recommendations & Opportunities"
    description="Google Ads recommendation inventory for optimization opportunities."
    endpoint="/analytics/google-ads/recommendations/"
  />
);

export default GoogleAdsRecommendationsPage;
