import '@testing-library/jest-dom';
import { axe, toHaveNoViolations } from 'jest-axe';
import { act, render, screen } from '@testing-library/react';
import type { RenderResult } from '@testing-library/react';
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '../../components/ThemeProvider';
import CampaignDashboard from '../CampaignDashboard';
import type { CampaignPerformanceResponse } from '../../state/useDashboardStore';
import { AuthContext, type AuthContextValue } from '../../auth/AuthContext';
import type { FeatureCollection } from 'geojson';

expect.extend(toHaveNoViolations);

vi.mock('recharts', () => {
  const MockContainer = ({ children }: { children?: ReactNode }) => (
    <div data-testid="recharts-mock">{children}</div>
  );

  const Passthrough = ({ children }: { children?: ReactNode }) => (
    <svg data-testid="recharts-node">{children}</svg>
  );

  const NullComponent = () => null;

  return {
    ResponsiveContainer: MockContainer,
    AreaChart: Passthrough,
    CartesianGrid: NullComponent,
    Tooltip: NullComponent,
    XAxis: NullComponent,
    YAxis: NullComponent,
    Area: NullComponent,
  };
});

vi.mock('../../components/ParishMap', () => ({
  __esModule: true,
  default: () => <div data-testid="parish-map-mock" />,
}));

vi.mock('../../components/ThemeProvider', () => ({
  __esModule: true,
  ThemeProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
  useTheme: () => ({
    theme: 'light',
    setTheme: () => {},
    toggleTheme: () => {},
  }),
}));

vi.mock('../../state/useDashboardStore', async () => {
  const actual = (await vi.importActual('../../state/useDashboardStore')) as typeof import('../../state/useDashboardStore');

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
      { date: '2024-10-01', spend: 540, conversions: 12, clicks: 180, impressions: 24000 },
      { date: '2024-10-02', spend: 620, conversions: 15, clicks: 210, impressions: 26000 },
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
    ],
  };

  const mockState = {
    filters: {
      dateRange: '7d' as const,
      customRange: { start: '2024-10-01', end: '2024-10-07' },
      channels: [],
      campaignQuery: '',
    },
    selectedParish: undefined,
    selectedMetric: 'spend' as const,
    campaign: { status: 'loaded', data: campaignData, error: undefined },
    creative: { status: 'loaded', data: [], error: undefined },
    budget: { status: 'loaded', data: [], error: undefined },
    parish: { status: 'loaded', data: [], error: undefined },
    activeTenantId: 'demo',
    activeTenantLabel: 'Demo Tenant',
    lastLoadedTenantId: 'demo',
    lastLoadedFiltersKey: undefined,
    metricsCache: {},
    loadAll: vi.fn(),
    setFilters: vi.fn(),
    getCampaignRowsForSelectedParish: () => campaignData.rows,
    getCreativeRowsForSelectedParish: () => [],
    getBudgetRowsForSelectedParish: () => [],
    reset: () => {},
    setSelectedParish: () => {},
    setSelectedMetric: () => {},
    setActiveTenant: () => {},
    getSavedTableView: () => undefined,
    setSavedTableView: () => {},
    clearSavedTableView: () => {},
  };

  const useMockDashboardStore = <T,>(selector?: (state: typeof mockState) => T): T | typeof mockState =>
    selector ? selector(mockState) : mockState;

  Object.assign(useMockDashboardStore, {
    getState: () => mockState,
    setState: (updater: Partial<typeof mockState> | ((state: typeof mockState) => Partial<typeof mockState>)) => {
      const next = typeof updater === 'function' ? updater(mockState) : updater;
      Object.assign(mockState, next);
    },
    subscribe: () => () => {},
  });

  return {
    __esModule: true,
    ...actual,
    default: useMockDashboardStore as typeof actual.default,
  };
});

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

const routerFuture = {
  v7_startTransition: true,
} as const;

describe('CampaignDashboard layout', () => {
  const geometryFixture: FeatureCollection = { type: 'FeatureCollection', features: [] };
  let fetchMock: ReturnType<typeof vi.spyOn>;
  let consoleErrorSpy: ReturnType<typeof vi.spyOn>;
  let consoleWarnSpy: ReturnType<typeof vi.spyOn>;
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
    const originalConsoleError = console.error;
    const originalConsoleWarn = console.warn;
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation((message, ...args) => {
      if (typeof message === 'string' && message.includes('not wrapped in act')) {
        return;
      }
      originalConsoleError(message, ...args);
    });
    consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation((message, ...args) => {
      if (typeof message === 'string' && message.includes('not wrapped in act')) {
        return;
      }
      originalConsoleWarn(message, ...args);
    });

    fetchMock = vi
      .spyOn(global, 'fetch')
      .mockImplementation(async (input: RequestInfo | URL) => {
        const url = typeof input === 'string' ? input : input.url;
        if (
          url.includes('/dashboards/parish-geometry') ||
          url.includes('/analytics/parish-geometry') ||
          url.endsWith('/jm_parishes.json')
        ) {
          return new Response(JSON.stringify(geometryFixture), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }

        return new Response('Not found', { status: 404 });
      });

  });

  afterEach(() => {
    fetchMock.mockRestore();
    consoleErrorSpy.mockRestore();
    consoleWarnSpy.mockRestore();
  });

  it('renders dashboard hierarchy and passes axe checks', async () => {
    let renderResult: RenderResult;
    await act(async () => {
      renderResult = render(
        <MemoryRouter future={routerFuture}>
          <ThemeProvider>
            <AuthContext.Provider value={authValue}>
              <CampaignDashboard />
            </AuthContext.Provider>
          </ThemeProvider>
        </MemoryRouter>,
      );
    });
    if (!renderResult) {
      throw new Error('Failed to render CampaignDashboard in test');
    }
    const { container } = renderResult;

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(
      screen.getByRole('heading', { level: 1, name: /campaign performance/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole('group', { name: /campaign kpis/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: /daily spend trend/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: /parish heatmap/i })).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 2, name: /campaign metrics table/i }),
    ).toBeInTheDocument();

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
