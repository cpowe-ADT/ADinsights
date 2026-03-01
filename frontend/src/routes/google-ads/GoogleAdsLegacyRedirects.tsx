import { Navigate, useParams } from 'react-router-dom';

export const GoogleAdsTabRedirect = ({
  tab,
  extra,
}: {
  tab: string;
  extra?: Record<string, string>;
}) => {
  const params = new URLSearchParams({ tab, ...(extra ?? {}) });
  return <Navigate to={`/dashboards/google-ads?${params.toString()}`} replace />;
};

export const GoogleAdsCampaignDrawerRedirect = () => {
  const { campaignId = '' } = useParams();
  const drawer = encodeURIComponent(`campaign:${campaignId}`);
  return <Navigate to={`/dashboards/google-ads?tab=campaigns&drawer=${drawer}`} replace />;
};

