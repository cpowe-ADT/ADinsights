import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

import { fetchGoogleAdsCampaignDetail } from '../../lib/googleAdsDashboard';

const GoogleAdsCampaignDetailPage = () => {
  const { campaignId = '' } = useParams();
  const [payload, setPayload] = useState<Record<string, unknown> | null>(null);
  const [status, setStatus] = useState<'idle' | 'loading' | 'error'>('loading');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!campaignId) {
      setStatus('error');
      setError('Campaign id is missing.');
      return;
    }

    let active = true;
    const load = async () => {
      setStatus('loading');
      setError('');
      try {
        const response = await fetchGoogleAdsCampaignDetail(campaignId);
        if (!active) {
          return;
        }
        setPayload(response);
        setStatus('idle');
      } catch (err) {
        if (!active) {
          return;
        }
        setStatus('error');
        setError(err instanceof Error ? err.message : 'Failed to load campaign detail.');
      }
    };

    void load();
    return () => {
      active = false;
    };
  }, [campaignId]);

  return (
    <section className="dashboardPage">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Google Ads</p>
        <h1 className="dashboardHeading">Campaign Drilldown</h1>
        <p className="dashboardSubtitle">Campaign ID: {campaignId}</p>
      </header>

      {status === 'loading' ? <div className="dashboard-state dashboard-state--page">Loading campaign...</div> : null}
      {status === 'error' ? (
        <div className="dashboard-state dashboard-state--page" role="alert">
          {error}
        </div>
      ) : null}

      {payload ? (
        <div className="panel">
          <h2>Campaign Payload</h2>
          <pre style={{ overflowX: 'auto' }}>{JSON.stringify(payload, null, 2)}</pre>
        </div>
      ) : null}
    </section>
  );
};

export default GoogleAdsCampaignDetailPage;
