import GoogleAdsDataTablePage from '../../components/google-ads/GoogleAdsDataTablePage';

const GoogleAdsPmaxPage = () => (
  <GoogleAdsDataTablePage
    eyebrow="Google Ads"
    title="Performance Max"
    description="Asset group performance and top drivers for Performance Max campaigns."
    endpoint="/analytics/google-ads/pmax/asset-groups/"
  />
);

export default GoogleAdsPmaxPage;
