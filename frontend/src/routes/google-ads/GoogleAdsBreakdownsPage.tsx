import { useState } from 'react';

import GoogleAdsDataTablePage from '../../components/google-ads/GoogleAdsDataTablePage';

const GoogleAdsBreakdownsPage = () => {
  const [dimension, setDimension] = useState('location');

  return (
    <div>
      <div className="panel" style={{ marginBottom: '1rem' }}>
        <label className="dashboard-field">
          <span className="dashboard-field__label">Breakdown</span>
          <select value={dimension} onChange={(event) => setDimension(event.target.value)}>
            <option value="location">Location</option>
            <option value="device">Device</option>
            <option value="time_of_day">Time of day</option>
            <option value="audience">Audience</option>
            <option value="demographic">Demographic</option>
          </select>
        </label>
      </div>
      <GoogleAdsDataTablePage
        eyebrow="Google Ads"
        title="Audiences, Demographics, Location, Device, Time"
        description="Breakdown table and top movers for selected dimensions."
        endpoint="/analytics/google-ads/breakdowns/"
        query={{ dimension }}
      />
    </div>
  );
};

export default GoogleAdsBreakdownsPage;
