import GoogleAdsDataTablePage from '../../components/google-ads/GoogleAdsDataTablePage';

const GoogleAdsCampaignsPage = () => (
  <GoogleAdsDataTablePage
    eyebrow="Google Ads"
    title="Performance by Campaign"
    description="Campaign-level metrics with pagination, sorting, and server-side aggregation."
    endpoint="/analytics/google-ads/campaigns/"
  />
);

export default GoogleAdsCampaignsPage;
