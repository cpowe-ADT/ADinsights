import type { Meta, StoryObj } from '@storybook/react';
import { useEffect, useRef, type ReactNode } from 'react';

import CampaignDashboard from './CampaignDashboard';
import { AuthContext, type AuthContextValue } from '../auth/AuthContext';
import { useTheme } from '../components/ThemeProvider';
import useDashboardStore from '../state/useDashboardStore';

const sampleCampaign = {
  summary: {
    currency: 'USD',
    totalSpend: 12890,
    totalImpressions: 420000,
    totalClicks: 1840,
    totalConversions: 265,
    averageRoas: 3.42,
  },
  trend: [
    {
      date: '2024-10-01',
      spend: 540,
      conversions: 12,
      clicks: 180,
      impressions: 24000,
    },
    {
      date: '2024-10-02',
      spend: 620,
      conversions: 15,
      clicks: 210,
      impressions: 26000,
    },
    {
      date: '2024-10-03',
      spend: 710,
      conversions: 18,
      clicks: 240,
      impressions: 28000,
    },
    {
      date: '2024-10-04',
      spend: 680,
      conversions: 22,
      clicks: 260,
      impressions: 30500,
    },
  ],
  rows: [
    {
      id: 'cmp-1',
      name: 'Awareness Boost',
      platform: 'Meta',
      status: 'Active',
      objective: 'Awareness',
      parish: 'Kingston',
      spend: 4800,
      impressions: 152000,
      clicks: 620,
      conversions: 88,
      roas: 2.4,
      ctr: 0.041,
      cpc: 3.87,
      cpm: 31.58,
    },
    {
      id: 'cmp-2',
      name: 'Conversion Surge',
      platform: 'Google',
      status: 'Paused',
      objective: 'Leads',
      parish: 'St. Andrew',
      spend: 2200,
      impressions: 98000,
      clicks: 420,
      conversions: 65,
      roas: 3.1,
      ctr: 0.043,
      cpc: 5.24,
      cpm: 22.45,
    },
    {
      id: 'cmp-3',
      name: 'Remarketing Push',
      platform: 'TikTok',
      status: 'Active',
      objective: 'Conversions',
      parish: 'St. James',
      spend: 1650,
      impressions: 72000,
      clicks: 310,
      conversions: 52,
      roas: 3.8,
      ctr: 0.043,
      cpc: 5.32,
      cpm: 22.92,
    },
  ],
};

const sampleParishAggregates = [
  { parish: 'Kingston', spend: 5400, impressions: 120000, clicks: 4200, conversions: 85, roas: 3.6 },
  { parish: 'St. Andrew', spend: 4200, impressions: 98000, clicks: 3600, conversions: 74, roas: 3.2 },
  { parish: 'St. James', spend: 3100, impressions: 76000, clicks: 2850, conversions: 62, roas: 3.4 },
];

const authValue: AuthContextValue = {
  status: 'authenticated',
  isAuthenticated: true,
  accessToken: 'story-token',
  tenantId: 'demo',
  user: { email: 'analyst@example.com' },
  login: async () => undefined,
  logout: () => undefined,
  statusMessage: undefined,
};

const ThemeWrapper = ({ theme, children }: { theme: 'light' | 'dark'; children: ReactNode }) => {
  const { setTheme } = useTheme();

  useEffect(() => {
    setTheme(theme);
  }, [setTheme, theme]);

  return <>{children}</>;
};

const StoreBootstrap = ({ children }: { children: ReactNode }) => {
  const storeSnapshot = useRef(useDashboardStore.getState());

  useEffect(() => {
    const originalFetch = window.fetch?.bind(window) ?? ((input: RequestInfo | URL, init?: RequestInit) =>
      fetch(input, init)
    );
    const initialSnapshot = storeSnapshot.current;

    window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.url;
      if (url.includes('/dashboards/parish-geometry/')) {
        return originalFetch('/jm_parishes.json', init);
      }
      return originalFetch(input, init);
    };

    useDashboardStore.setState((state) => ({
      ...state,
      selectedParish: undefined,
      selectedMetric: 'spend',
      loadAll: async () => undefined,
      campaign: { status: 'loaded', data: sampleCampaign },
      creative: { status: 'loaded', data: [] },
      budget: { status: 'loaded', data: [] },
      parish: { status: 'loaded', data: sampleParishAggregates },
    }));

    return () => {
      window.fetch = originalFetch;
      useDashboardStore.setState(initialSnapshot, true);
    };
  }, []);

  return <>{children}</>;
};

const meta: Meta<typeof CampaignDashboard> = {
  title: 'Routes/CampaignDashboard',
  component: CampaignDashboard,
  parameters: {
    layout: 'fullscreen',
    chromatic: { viewports: [375, 1280] },
  },
};

export default meta;

type Story = StoryObj<typeof CampaignDashboard>;

const renderDashboard = () => (
  <AuthContext.Provider value={authValue}>
    <StoreBootstrap>
      <CampaignDashboard />
    </StoreBootstrap>
  </AuthContext.Provider>
);

export const Light: Story = {
  render: renderDashboard,
};

export const Dark: Story = {
  render: () => <ThemeWrapper theme="dark">{renderDashboard()}</ThemeWrapper>,
};
