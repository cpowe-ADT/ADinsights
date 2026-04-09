import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import * as React from 'react';
import type { FeatureCollection } from 'geojson';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('react-leaflet', () => {
  const { forwardRef, useEffect, useImperativeHandle, useRef, useState } = React;

  type LayerRecord = {
    name: string;
    handlers: Record<string, () => void>;
    layer: {
      feature: unknown;
      options: Record<string, unknown>;
      setStyle: (style: Record<string, unknown>) => void;
      bindTooltip: (content: string) => { setContent: (content: string) => void };
      getTooltip: () => { setContent: (content: string) => void } | undefined;
      on: (events: Record<string, () => void>) => void;
    };
  };

  const MapContainer = ({ children }: { children: React.ReactNode }) => (
    <div data-testid="map-container">{children}</div>
  );

  const TileLayer = () => null;

  const GeoJSON = forwardRef(
    (
      {
        data,
        onEachFeature,
      }: {
        data?: FeatureCollection;
        onEachFeature?: (feature: unknown, layer: unknown) => void;
      },
      ref: React.ForwardedRef<{ eachLayer: (callback: (layer: unknown) => void) => void }>,
    ) => {
      const layersRef = useRef<LayerRecord[]>([]);
      const [, forceRender] = useState(0);

      useEffect(() => {
        layersRef.current = [];

        if (data && Array.isArray((data as FeatureCollection).features)) {
          for (const feature of (data as FeatureCollection).features) {
            const name =
              typeof feature === 'object' &&
              feature !== null &&
              typeof (feature as { properties?: { name?: unknown } }).properties === 'object'
                ? (((
                    (feature as { properties?: { name?: unknown } }).properties as {
                      name?: unknown;
                    }
                  ).name as string) ?? 'Unknown')
                : 'Unknown';

            const handlers: Record<string, () => void> = {};
            const tooltip = {
              setContent(next: string) {
                tooltipContent = next;
              },
            };
            let tooltipContent = '';

            const layer = {
              feature,
              options: { weight: 1 },
              setStyle(style: Record<string, unknown>) {
                layer.options = { ...layer.options, ...style };
              },
              bindTooltip(content: string) {
                tooltipContent = content;
                return tooltip;
              },
              getTooltip() {
                return tooltipContent ? tooltip : undefined;
              },
              on(events: Record<string, () => void>) {
                Object.assign(handlers, events);
              },
            };

            layersRef.current.push({ name, handlers, layer });
            onEachFeature?.(feature, layer);
          }
        }

        forceRender((value: number) => value + 1);
      }, [data, onEachFeature]);

      useImperativeHandle(
        ref,
        () => ({
          eachLayer(callback: (layer: unknown) => void) {
            for (const record of layersRef.current) {
              callback(record.layer);
            }
          },
        }),
        [],
      );

      return (
        <div data-testid="geojson-layer">
          {layersRef.current.map((record: LayerRecord) => (
            <button
              key={record.name}
              type="button"
              data-testid={`parish-feature-${record.name}`}
              onClick={() => record.handlers.click?.()}
            >
              {record.name}
            </button>
          ))}
        </div>
      );
    },
  );

  GeoJSON.displayName = 'MockGeoJSON';

  return { MapContainer, TileLayer, GeoJSON };
});

vi.mock('leaflet', () => {
  type Feature = import('geojson').Feature;

  const createLayerStub = (feature: Feature) => {
    return {
      feature,
      options: { weight: 1 },
      setStyle: () => {},
      bindTooltip: () => ({ setContent: () => {} }),
      getTooltip: () => undefined,
      on: () => {},
      once: (_event: string, callback: () => void) => callback(),
      getElement: () => ({ setAttribute: () => {} }),
    } as unknown;
  };

  const api = {
    map: (node: HTMLElement) => {
      return {
        _container: node,
        invalidateSize: () => {},
        remove: () => {},
        getContainer: () => node,
        scrollWheelZoom: {
          enable: () => {},
          disable: () => {},
        },
      } as unknown;
    },
    tileLayer: () => ({
      addTo: () => {},
      remove: () => {},
    }),
    geoJSON: (
      data: import('geojson').FeatureCollection,
      options?: { onEachFeature?: (feature: Feature, layer: unknown) => void },
    ) => {
      return {
        addTo: () => {},
        remove: () => {},
        eachLayer: (callback: (layer: unknown) => void) => {
          for (const feature of data?.features ?? []) {
            const layer = createLayerStub(feature);
            options?.onEachFeature?.(feature, layer);
            callback(layer);
          }
        },
      };
    },
    point: (x: number, y: number) => ({ x, y }),
  };

  return {
    ...api,
    default: api,
  };
});

vi.mock('recharts', () => {
  const MockContainer = ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="recharts-mock">{children}</div>
  );
  const Passthrough = ({ children }: { children?: React.ReactNode }) => (
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

type AppModule = typeof import('./App');
type AuthModule = typeof import('./auth/AuthContext');
type ThemeModule = typeof import('./components/ThemeProvider');
type StoreModule = typeof import('./state/useDashboardStore');

let App: AppModule['default'];
let AuthProvider: AuthModule['AuthProvider'];
let ThemeProvider: ThemeModule['ThemeProvider'];
let useDashboardStore: StoreModule['default'];

const campaignPayload = {
  summary: {
    currency: 'JMD',
    totalSpend: 1000,
    totalImpressions: 2000,
    totalClicks: 300,
    totalConversions: 40,
    averageRoas: 3.2,
  },
  trend: [
    { date: '2024-09-01', spend: 100, conversions: 4, clicks: 20, impressions: 200 },
    { date: '2024-09-02', spend: 120, conversions: 5, clicks: 22, impressions: 240 },
  ],
  rows: [
    {
      id: 'cmp_kingston',
      name: 'Kingston Awareness',
      platform: 'Meta',
      status: 'Active',
      parishes: ['Kingston'],
      spend: 500,
      impressions: 1000,
      clicks: 150,
      conversions: 20,
      roas: 3.4,
      ctr: 0.15,
      cpc: 3.33,
      cpm: 500,
    },
    {
      id: 'cmp_montego_bay',
      name: 'Montego Bay Prospecting',
      platform: 'Google Ads',
      status: 'Active',
      parishes: ['St James'],
      spend: 350,
      impressions: 800,
      clicks: 120,
      conversions: 15,
      roas: 2.9,
      ctr: 0.12,
      cpc: 2.91,
      cpm: 437.5,
    },
  ],
};

const creativePayload = [
  {
    id: 'cr_test',
    name: 'Hero Unit',
    campaignId: 'cmp_kingston',
    campaignName: 'Kingston Awareness',
    platform: 'Meta',
    parishes: ['Kingston'],
    spend: 120,
    impressions: 450,
    clicks: 40,
    conversions: 6,
    roas: 3.1,
    ctr: 0.089,
  },
  {
    id: 'cr_test_2',
    name: 'Carousel',
    campaignId: 'cmp_montego_bay',
    campaignName: 'Montego Bay Prospecting',
    platform: 'Google Ads',
    parishes: ['St James'],
    spend: 95,
    impressions: 320,
    clicks: 30,
    conversions: 4,
    roas: 2.8,
    ctr: 0.094,
  },
];

const budgetPayload = [
  {
    id: 'budget_test',
    campaignName: 'Test Campaign',
    parishes: ['Kingston'],
    monthlyBudget: 200,
    spendToDate: 140,
    projectedSpend: 210,
    pacingPercent: 1.05,
  },
];

const parishPayload = [
  {
    parish: 'Kingston',
    spend: 500,
    impressions: 1000,
    clicks: 150,
    conversions: 20,
    roas: 3.4,
    campaignCount: 1,
    currency: 'JMD',
  },
  {
    parish: 'St James',
    spend: 350,
    impressions: 800,
    clicks: 120,
    conversions: 15,
    roas: 2.9,
    campaignCount: 1,
    currency: 'JMD',
  },
];

const metricsPayload = {
  metrics: {
    campaign_metrics: campaignPayload,
    creative_metrics: creativePayload,
    budget_metrics: budgetPayload,
    parish_metrics: parishPayload,
  },
  tenant_id: 'tenant-123',
  generated_at: '2024-09-05T00:00:00Z',
  coverage: {
    startDate: '2024-09-01',
    endDate: '2024-09-05',
  },
  availability: {
    campaign: { status: 'available', reason: null },
    creative: { status: 'available', reason: null },
    budget: { status: 'available', reason: null },
    parish_map: { status: 'available', reason: null, coverage_percent: 0.75 },
  },
};

const tenantFixtures = [
  { id: 'demo', name: 'Demo Retail Co.', status: 'active' },
  { id: 'tenant-123', name: 'Tenant 123 Holdings', status: 'active' },
  { id: 'sandbox', name: 'Sandbox Marketing Group', status: 'inactive' },
];

const geojsonPayload: FeatureCollection = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: { name: 'Kingston' },
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [-76.8, 17.9],
            [-76.7, 17.9],
            [-76.7, 18.0],
            [-76.8, 18.0],
            [-76.8, 17.9],
          ],
        ],
      },
    },
    {
      type: 'Feature',
      properties: { name: 'St James' },
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [-77.0, 18.3],
            [-76.9, 18.3],
            [-76.9, 18.4],
            [-77.0, 18.4],
            [-77.0, 18.3],
          ],
        ],
      },
    },
  ],
};

const createResponse = (body: unknown, init?: ResponseInit) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });

const createJwt = (exp = Math.floor(Date.now() / 1000) + 7_200) => {
  const encode = (value: object) =>
    btoa(JSON.stringify(value))
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=+$/g, '');
  return `${encode({ alg: 'HS256', typ: 'JWT' })}.${encode({ exp })}.signature`;
};

const resolveRequestUrl = (input: RequestInfo | URL): string => {
  if (typeof input === 'string') {
    return input;
  }
  if (input instanceof URL) {
    return input.toString();
  }
  if (
    typeof input === 'object' &&
    input !== null &&
    'url' in input &&
    typeof (input as { url?: unknown }).url === 'string'
  ) {
    return (input as Request).url;
  }
  return '';
};

const resolveRequestMethod = (input: RequestInfo | URL, init?: RequestInit): string => {
  if (init?.method) {
    return init.method;
  }
  if (
    typeof input === 'object' &&
    input !== null &&
    'method' in input &&
    typeof (input as { method?: unknown }).method === 'string'
  ) {
    return (input as Request).method;
  }
  return 'GET';
};

const resolveRequestHeader = (
  call: [RequestInfo | URL, RequestInit | undefined] | undefined,
  headerName: string,
): string | null => {
  if (!call) {
    return null;
  }

  const fromInit = call[1]?.headers;
  if (fromInit instanceof Headers) {
    return fromInit.get(headerName);
  }
  if (fromInit && typeof fromInit === 'object' && !Array.isArray(fromInit)) {
    const value = (fromInit as Record<string, string | undefined>)[headerName];
    if (typeof value === 'string') {
      return value;
    }
  }

  const requestLike = call[0];
  if (requestLike instanceof Request) {
    return requestLike.headers.get(headerName);
  }

  return null;
};

const expectHomeOrDashboardHeading = async () => {
  await waitFor(() => {
    const hero =
      screen.queryByRole('heading', { level: 1, name: /welcome back to adinsights/i }) ??
      screen.queryByRole('heading', { level: 1, name: /adinsights analytics/i }) ??
      screen.queryByRole('heading', { level: 1, name: /campaign performance/i }) ??
      screen.queryByRole('heading', { level: 1, name: /saved dashboards/i });
    expect(hero).toBeTruthy();
  });
};

describe('App integration', () => {
  beforeEach(async () => {
    vi.unstubAllEnvs();
    vi.stubEnv('VITE_MOCK_MODE', 'false');
    window.localStorage.clear();
    window.history.pushState({}, '', '/');

    const appModule: AppModule = await import('./App');
    App = appModule.default;
    const authModule: AuthModule = await import('./auth/AuthContext');
    AuthProvider = authModule.AuthProvider;
    const themeModule: ThemeModule = await import('./components/ThemeProvider');
    ThemeProvider = themeModule.ThemeProvider;
    const storeModule: StoreModule = await import('./state/useDashboardStore');
    useDashboardStore = storeModule.default;

    vi.restoreAllMocks();
    vi.clearAllMocks();
    useDashboardStore.getState().reset();

    class ResizeObserverMock {
      observe() {}
      unobserve() {}
      disconnect() {}
    }

    vi.stubGlobal('ResizeObserver', ResizeObserverMock);
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it('signs in and renders the authenticated home workspace', async () => {
    const recentDashboards = [
      {
        id: 'saved-home-1',
        name: 'Revenue overview',
        owner: 'Growth team',
        last_viewed_label: 'Moments ago',
        href: '/dashboards/saved/saved-home-1',
      },
    ];

    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = resolveRequestUrl(input);
      const method = resolveRequestMethod(input, init);

      if (url.endsWith('/api/auth/login/') && method === 'POST') {
        return Promise.resolve(
          createResponse({
            access: createJwt(),
            refresh: 'refresh-token-123',
            tenant_id: 'tenant-123',
            user: { email: 'user@example.com' },
          }),
        );
      }

      if (url.includes('/api/dashboards/recent/') && method === 'GET') {
        return Promise.resolve(createResponse(recentDashboards));
      }

      return Promise.reject(new Error(`Unhandled fetch: ${url}`));
    });

    vi.stubGlobal('fetch', fetchMock as typeof fetch);

    render(
      <ThemeProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </ThemeProvider>,
    );

    await userEvent.type(screen.getByLabelText(/email/i), 'user@example.com');
    await userEvent.type(screen.getByLabelText(/password/i), 'password123');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await expectHomeOrDashboardHeading();
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/dashboards/recent/'),
        expect.objectContaining({ method: 'GET' }),
      );
    });

    expect(await screen.findByText('Revenue overview')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: /quick actions/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /view campaigns/i })).toBeInTheDocument();
  });

  it('restores stored auth state and validates the session on app boot', async () => {
    const accessToken = createJwt();
    window.localStorage.setItem(
      'adinsights.auth',
      JSON.stringify({
        access: accessToken,
        refresh: 'refresh-token-456',
        tenantId: 'tenant-123',
        user: { email: 'user@example.com' },
      }),
    );

    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = resolveRequestUrl(input);
      const method = resolveRequestMethod(input, init);

      if (url.endsWith('/api/health/') && method === 'GET') {
        return Promise.resolve(createResponse({ status: 'ok' }));
      }

      if (url.endsWith('/api/me/') && method === 'GET') {
        return Promise.resolve(
          createResponse({
            email: 'user@example.com',
            tenant_id: 'tenant-123',
            roles: ['ADMIN'],
          }),
        );
      }

      if (url.includes('/api/dashboards/recent/') && method === 'GET') {
        return Promise.resolve(
          createResponse([
            {
              id: 'saved-home-2',
              name: 'Validated dashboard',
              owner: 'Ops',
              last_viewed_label: 'Today',
              href: '/dashboards/saved/saved-home-2',
            },
          ]),
        );
      }

      return Promise.reject(new Error(`Unhandled fetch: ${url}`));
    });

    vi.stubGlobal('fetch', fetchMock as typeof fetch);

    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ThemeProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </ThemeProvider>,
    );

    await expectHomeOrDashboardHeading();
    await waitFor(() => {
      const meCall = fetchMock.mock.calls.find(
        (call) => typeof call[0] === 'string' && call[0].includes('/api/me/'),
      );
      const recentDashboardsCall = fetchMock.mock.calls.find(
        (call) => typeof call[0] === 'string' && call[0].includes('/api/dashboards/recent/'),
      );
      expect(meCall).toBeTruthy();
      expect(recentDashboardsCall).toBeTruthy();
    });

    const meCall = fetchMock.mock.calls.find(
      (call) => typeof call[0] === 'string' && call[0].includes('/api/me/'),
    ) as [RequestInfo | URL, RequestInit | undefined] | undefined;
    const recentDashboardsCall = fetchMock.mock.calls.find(
      (call) => typeof call[0] === 'string' && call[0].includes('/api/dashboards/recent/'),
    ) as [RequestInfo | URL, RequestInit | undefined] | undefined;

    expect(resolveRequestHeader(recentDashboardsCall, 'Authorization')).toBe(
      `Bearer ${accessToken}`,
    );
    expect(await screen.findByText('Validated dashboard')).toBeInTheDocument();

    expect(consoleErrorSpy).not.toHaveBeenCalled();
    consoleErrorSpy.mockRestore();
  });
});
