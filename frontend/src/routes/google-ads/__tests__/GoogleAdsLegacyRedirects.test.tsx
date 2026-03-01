import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import {
  GoogleAdsCampaignDrawerRedirect,
  GoogleAdsTabRedirect,
} from '../GoogleAdsLegacyRedirects';

const LocationProbe = () => {
  const location = useLocation();
  return (
    <div data-testid="location-probe">
      {location.pathname}
      {location.search}
    </div>
  );
};

describe('Google Ads legacy redirects', () => {
  it('redirects legacy keywords route to unified workspace search tab query', async () => {
    render(
      <MemoryRouter initialEntries={['/dashboards/google-ads/keywords']}>
        <Routes>
          <Route
            path="/dashboards/google-ads/keywords"
            element={<GoogleAdsTabRedirect tab="search" extra={{ search_mode: 'keywords' }} />}
          />
          <Route path="/dashboards/google-ads" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('location-probe').textContent).toBe(
        '/dashboards/google-ads?tab=search&search_mode=keywords',
      );
    });
  });

  it('redirects legacy campaign detail route to unified workspace campaign drawer query', async () => {
    render(
      <MemoryRouter initialEntries={['/dashboards/google-ads/campaigns/12345']}>
        <Routes>
          <Route path="/dashboards/google-ads/campaigns/:campaignId" element={<GoogleAdsCampaignDrawerRedirect />} />
          <Route path="/dashboards/google-ads" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('location-probe').textContent).toBe(
        '/dashboards/google-ads?tab=campaigns&drawer=campaign%3A12345',
      );
    });
  });
});

