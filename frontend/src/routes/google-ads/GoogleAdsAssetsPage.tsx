import GoogleAdsDataTablePage from '../../components/google-ads/GoogleAdsDataTablePage';

const GoogleAdsAssetsPage = () => (
  <GoogleAdsDataTablePage
    eyebrow="Google Ads"
    title="Ads & Assets"
    description="Ad policy diagnostics and asset-level performance signals."
    endpoint="/analytics/google-ads/assets/"
  />
);

export default GoogleAdsAssetsPage;
