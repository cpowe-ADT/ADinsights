import '@testing-library/jest-dom';
import { axe, toHaveNoViolations } from 'jest-axe';
import { render, screen, waitFor } from '@testing-library/react';
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '../../components/ThemeProvider';
import CampaignDashboard from '../CampaignDashboard';
import useDashboardStore from '../../state/useDashboardStore';
import type { CampaignPerformanceResponse } from '../../state/useDashboardStore';
import { AuthContext, type AuthContextValue } from '../../auth/AuthContext';
import type { FeatureCollection } from 'geojson';

expect.extend(toHaveNoViolations);

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

describe('CampaignDashboard layout', () => {
  const initialState = useDashboardStore.getState();
  const geometryFixture: FeatureCollection = { type: 'FeatureCollection', features: [] };
  let fetchMock: ReturnType<typeof vi.spyOn>;
  const authValue: AuthContextValue = {
    status: 'authenticated',
    isAuthenticated: true,
    accessToken: 'test-token',
    tenantId: 'demo',
    user: { email: 'analyst@example.com' },
    login: vi.fn(),
    logout: vi.fn(),
    statusMessage: undefined,
  };

  beforeAll(() => {
    vi.stubGlobal('ResizeObserver', ResizeObserverMock);
    if (!('matchMedia' in window)) {
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        value: (query: string) => ({
          matches: false,
          media: query,
          onchange: null,
          addListener: () => {},
          removeListener: () => {},
          addEventListener: () => {},
          removeEventListener: () => {},
          dispatchEvent: () => false,
        }),
      });
    }
  });

  afterAll(() => {
    vi.unstubAllGlobals();
  });

  beforeEach(() => {
    const campaignData: CampaignPerformanceResponse = {
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
      ],
    };

    fetchMock = vi
      .spyOn(global, 'fetch')
      .mockImplementation(async (input: RequestInfo | URL) => {
        const url = typeof input === 'string' ? input : input.url;
        if (url.includes('/analytics/parish-geometry') || url.endsWith('/jm_parishes.json')) {
          return new Response(JSON.stringify(geometryFixture), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }

        return new Response('Not found', { status: 404 });
      });

    useDashboardStore.setState((state) => ({
      ...state,
      selectedParish: undefined,
      selectedMetric: 'spend',
      loadAll: vi.fn(),
      campaign: { status: 'loaded', data: campaignData },
      creative: { status: 'loaded', data: [] },
      budget: { status: 'loaded', data: [] },
      parish: { status: 'loaded', data: [] },
    }));
  });

  afterEach(() => {
    fetchMock.mockRestore();
    useDashboardStore.setState(initialState, true);
  });

  it('renders dashboard hierarchy and passes axe checks', async () => {
    const { container } = render(
      <MemoryRouter>
        <ThemeProvider>
          <AuthContext.Provider value={authValue}>
            <CampaignDashboard />
          </AuthContext.Provider>
        </ThemeProvider>
      </MemoryRouter>,
    );

    expect(
      screen.getByRole('heading', { level: 1, name: /campaign performance/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole('group', { name: /campaign kpis/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: /daily spend trend/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: /parish heatmap/i })).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 2, name: /campaign metrics table/i }),
    ).toBeInTheDocument();

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
