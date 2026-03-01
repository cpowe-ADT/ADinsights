import GoogleAdsDataTablePage from '../../components/google-ads/GoogleAdsDataTablePage';

const GoogleAdsConversionsPage = () => (
  <GoogleAdsDataTablePage
    eyebrow="Google Ads"
    title="Conversions & Attribution"
    description="Conversion action reporting with action-level conversion and value trends."
    endpoint="/analytics/google-ads/conversions/actions/"
  />
);

export default GoogleAdsConversionsPage;
