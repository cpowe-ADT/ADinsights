import GoogleAdsDataTablePage from '../../components/google-ads/GoogleAdsDataTablePage';

const GoogleAdsChannelsPage = () => (
  <GoogleAdsDataTablePage
    eyebrow="Google Ads"
    title="Channel Views"
    description="Search, Display, Video, Shopping, Performance Max, and other channel rollups."
    endpoint="/analytics/google-ads/channels/"
  />
);

export default GoogleAdsChannelsPage;
