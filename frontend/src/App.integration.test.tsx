import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { act } from 'react';
import type { FeatureCollection } from 'geojson';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('react-leaflet', () => {
  const React = require('react') as typeof import('react');
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
      parish: 'Kingston',
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
      parish: 'St James',
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
    parish: 'Kingston',
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
    parish: 'St James',
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
};

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

describe('App integration', () => {
  beforeEach(async () => {
    vi.resetModules();
    vi.unstubAllEnvs();
    vi.stubEnv('VITE_MOCK_MODE', 'false');

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
    window.localStorage.clear();
    window.history.pushState({}, '', '/');
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

  it('signs in, loads live metrics, and filters by parish selection', async () => {
    const accessToken = 'access-token-123';

    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url =
        typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
      const method =
        init?.method ??
        (typeof input === 'object' && 'method' in input ? (input as Request).method : 'GET');

      if (url.endsWith('/api/auth/login/') && method === 'POST') {
        return Promise.resolve(
          createResponse({
            access: accessToken,
            refresh: 'refresh-token-123',
            tenant_id: 'tenant-123',
            user: { email: 'user@example.com' },
          }),
        );
      }

      if (url.includes('/api/metrics/combined/') && method === 'GET') {
        return Promise.resolve(createResponse(metricsPayload));
      }

      if (url.endsWith('/jm_parishes.json') || url.includes('/api/dashboards/parish-geometry/')) {
        return Promise.resolve(createResponse(geojsonPayload));
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

    const heroHeading = await screen.findByRole('heading', { name: /adinsights analytics/i });
    expect(heroHeading).toBeInTheDocument();

    const campaignCard = screen.getByText(/Campaign performance/i).closest('article');
    expect(campaignCard).not.toBeNull();
    await userEvent.click(
      within(campaignCard as HTMLElement).getByRole('button', { name: /open/i }),
    );

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/metrics/combined/'),
        expect.objectContaining({ method: 'GET' }),
      ),
    );

    const metricsCall = fetchMock.mock.calls.find(
      (call) => typeof call[0] === 'string' && call[0].includes('/api/metrics/combined/'),
    );
    expect(metricsCall).toBeTruthy();
    const metricsHeaders = metricsCall?.[1]?.headers as Headers | undefined;
    expect(metricsHeaders?.get('Authorization')).toBe(`Bearer ${accessToken}`);

    const campaignOccurrences = await screen.findAllByText('Kingston Awareness');
    expect(campaignOccurrences.length).toBeGreaterThan(0);
    expect(screen.getAllByText('Montego Bay Prospecting').length).toBeGreaterThan(0);

    const mapFeature = await screen.findByTestId('parish-feature-Kingston');
    await userEvent.click(mapFeature);

    const tableCard = screen
      .getByRole('heading', { name: /campaign performance/i })
      .closest('.table-card');
    expect(tableCard).not.toBeNull();
    await waitFor(() =>
      expect(
        within(tableCard as HTMLElement).getByText(
          (_, element) =>
            element?.tagName === 'P' && element.textContent?.includes('Filtering to Kingston'),
        ),
      ).toBeInTheDocument(),
    );
    const filteredRows = screen.getAllByText('Kingston Awareness');
    expect(filteredRows.length).toBeGreaterThan(0);
    expect(screen.queryByText('Montego Bay Prospecting')).not.toBeInTheDocument();

    const clearFilterButton = within(tableCard as HTMLElement).getByRole('button', {
      name: /^clear$/i,
    });
    await userEvent.click(clearFilterButton);
    await waitFor(() =>
      expect(screen.getAllByText('Montego Bay Prospecting').length).toBeGreaterThan(0),
    );

    await userEvent.click(screen.getByRole('link', { name: /creatives/i }));
    expect(await screen.findByText('Top creatives')).toBeInTheDocument();
    expect(screen.getByText(/Hero Unit/)).toBeInTheDocument();
  });

  it('surfaces metrics API errors across the dashboard without console noise', async () => {
    let metricsCallCount = 0;

    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url =
        typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
      const method =
        init?.method ??
        (typeof input === 'object' && 'method' in input ? (input as Request).method : 'GET');

      if (url.endsWith('/api/auth/login/') && method === 'POST') {
        return Promise.resolve(
          createResponse({
            access: 'access-token-456',
            refresh: 'refresh-token-456',
            tenant_id: 'tenant-123',
            user: { email: 'user@example.com' },
          }),
        );
      }

      if (url.includes('/api/metrics/combined/') && method === 'GET') {
        metricsCallCount += 1;
        if (metricsCallCount === 1) {
          return Promise.resolve(createResponse(metricsPayload));
        }
        return Promise.resolve(
          createResponse({ detail: 'Metrics service unavailable' }, { status: 503 }),
        );
      }

      if (url.endsWith('/jm_parishes.json') || url.includes('/api/dashboards/parish-geometry/')) {
        return Promise.resolve(createResponse(geojsonPayload));
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

    await userEvent.type(screen.getByLabelText(/email/i), 'user@example.com');
    await userEvent.type(screen.getByLabelText(/password/i), 'password123');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

    const heroHeading = await screen.findByRole('heading', { name: /adinsights analytics/i });
    expect(heroHeading).toBeInTheDocument();

    const campaignCard = screen.getByText(/Campaign performance/i).closest('article');
    expect(campaignCard).not.toBeNull();
    await userEvent.click(
      within(campaignCard as HTMLElement).getByRole('button', { name: /open/i }),
    );

    const initialRows = await screen.findAllByText('Kingston Awareness');
    expect(initialRows.length).toBeGreaterThan(0);

    await act(async () => {
      await useDashboardStore.getState().loadAll(undefined, { force: true });
    });

    const errorMessage = 'Metrics service unavailable';

    const alerts = await screen.findAllByRole('alert');
    expect(alerts.some((node) => node.textContent?.includes(errorMessage))).toBe(true);

    expect(consoleErrorSpy).not.toHaveBeenCalled();
    consoleErrorSpy.mockRestore();
  });
});
