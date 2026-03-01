import GoogleAdsDataTablePage from '../../components/google-ads/GoogleAdsDataTablePage';

const GoogleAdsChangeLogPage = () => (
  <GoogleAdsDataTablePage
    eyebrow="Google Ads"
    title="Change Log & Governance"
    description="Recent account-level changes (bids, budgets, ads, targeting) and metadata."
    endpoint="/analytics/google-ads/change-events/"
  />
);

export default GoogleAdsChangeLogPage;
