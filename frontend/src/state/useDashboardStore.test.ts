import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const campaignData = {
  summary: {
    currency: 'JMD',
    totalSpend: 100,
    totalImpressions: 200,
    totalClicks: 30,
    totalConversions: 4,
    averageRoas: 3.2,
  },
  trend: [],
  rows: [
    {
      id: 'cmp_test',
      name: 'Test',
      platform: 'Meta',
      status: 'Active',
      parish: 'Kingston',
      spend: 100,
      impressions: 200,
      clicks: 30,
      conversions: 4,
      roas: 3.2,
    },
  ],
};

const creativeData = [
  {
    id: 'cr_test',
    name: 'Creative',
    campaignId: 'cmp_test',
    campaignName: 'Test',
    platform: 'Meta',
    parish: 'Kingston',
    spend: 40,
    impressions: 120,
    clicks: 12,
    conversions: 2,
    roas: 2.5,
  },
];

const budgetData = [
  {
    id: 'budget_test',
    campaignName: 'Test',
    parishes: ['Kingston'],
    monthlyBudget: 200,
    spendToDate: 120,
    projectedSpend: 210,
    pacingPercent: 1.05,
  },
];

const parishData = [
  {
    parish: 'Kingston',
    spend: 100,
    impressions: 200,
    clicks: 30,
    conversions: 4,
    roas: 3.2,
    campaignCount: 1,
    currency: 'JMD',
  },
];

describe('useDashboardStore', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
    vi.stubEnv('VITE_MOCK_MODE', 'true');
  });

  afterEach(async () => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    if (originalFetch) {
      globalThis.fetch = originalFetch;
    } else {
      Reflect.deleteProperty(globalThis as typeof globalThis & { fetch?: unknown }, 'fetch');
    }

    const { useDatasetStore } = await import('./useDatasetStore');
    useDatasetStore.setState({
      mode: 'live',
      adapters: [],
      status: 'idle',
      error: undefined,
      source: undefined,
      demoTenants: [],
      demoTenantId: undefined,
    });
  });

  it('loads dashboard data from the mock endpoints', async () => {
    const fetchMock = vi.fn((url: RequestInfo | URL) => {
      if (
        typeof url === 'string' &&
        (url.endsWith('/sample_campaign_performance.json') ||
          url.includes('/analytics/campaign-performance/'))
      ) {
        return Promise.resolve(
          new Response(JSON.stringify(campaignData), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        );
      }
      if (
        typeof url === 'string' &&
        (url.endsWith('/sample_creative_performance.json') ||
          url.includes('/analytics/creative-performance/'))
      ) {
        return Promise.resolve(
          new Response(JSON.stringify(creativeData), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        );
      }
      if (
        typeof url === 'string' &&
        (url.endsWith('/sample_budget_pacing.json') || url.includes('/analytics/budget-pacing/'))
      ) {
        return Promise.resolve(
          new Response(JSON.stringify(budgetData), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        );
      }
      if (
        typeof url === 'string' &&
        (url.endsWith('/sample_parish_aggregates.json') ||
          url.includes('/analytics/parish-performance/'))
      ) {
        return Promise.resolve(
          new Response(JSON.stringify(parishData), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        );
      }
      return Promise.reject(new Error(`Unhandled fetch: ${String(url)}`));
    });
    globalThis.fetch = fetchMock as typeof globalThis.fetch;

    const { default: useDashboardStore } = await import('./useDashboardStore');

    await useDashboardStore.getState().loadAll('tenant-123');

    const state = useDashboardStore.getState();
    expect(state.campaign.data?.rows).toHaveLength(1);
    expect(state.creative.data).toHaveLength(1);
    expect(state.budget.data).toHaveLength(1);
    expect(state.parish.data).toHaveLength(1);
    expect(state.getCampaignRowsForSelectedParish()).toHaveLength(1);
    expect(state.getCachedMetrics('tenant-123')).toBeDefined();
    expect(state.selectedParish).toBeUndefined();
  });

  it('loads aggregated metrics and reuses the tenant cache when mock mode is disabled', async () => {
    vi.stubEnv('VITE_MOCK_MODE', 'false');

    const snapshotResponse = {
      metrics: {
        campaign_metrics: campaignData,
        creative_metrics: creativeData,
        budget_metrics: budgetData,
        parish_metrics: parishData,
      },
      tenant_id: 'tenant-xyz',
      generated_at: '2024-09-05T00:00:00Z',
    } satisfies Record<string, unknown>;

    const fetchMock = vi
      .fn<(url: RequestInfo | URL) => Promise<Response>>()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(snapshotResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockRejectedValueOnce(new Error('Service unavailable'));

    globalThis.fetch = fetchMock as typeof globalThis.fetch;

    const { default: useDashboardStore } = await import('./useDashboardStore');

    await useDashboardStore.getState().loadAll('tenant-xyz');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const requestUrl = fetchMock.mock.calls[0]?.[0];
    expect(typeof requestUrl === 'string' ? requestUrl : String(requestUrl)).toContain(
      '/api/metrics/combined/',
    );

    let state = useDashboardStore.getState();
    expect(state.campaign.status).toBe('loaded');
    expect(state.campaign.data?.rows).toHaveLength(1);
    expect(state.getCampaignRowsForSelectedParish()).toHaveLength(1);
    state.setSelectedParish('Kingston');
    expect(state.getCampaignRowsForSelectedParish()).toHaveLength(1);
    expect(state.getCachedMetrics('tenant-xyz')?.campaign.rows).toHaveLength(1);

    await useDashboardStore.getState().loadAll('tenant-xyz');

    expect(fetchMock).toHaveBeenCalledTimes(1);

    await useDashboardStore.getState().loadAll('tenant-xyz', { force: true });

    expect(fetchMock).toHaveBeenCalledTimes(2);

    state = useDashboardStore.getState();
    expect(state.campaign.status).toBe('error');
    expect(state.campaign.data?.rows).toHaveLength(1);
    expect(state.campaign.error).toContain('Service unavailable');

    await useDashboardStore.getState().loadAll('tenant-xyz');

    expect(fetchMock).toHaveBeenCalledTimes(2);

    state = useDashboardStore.getState();
    expect(state.campaign.status).toBe('loaded');
    expect(state.campaign.data?.rows).toHaveLength(1);
  });

  it('filters local rows by channel and campaign query', async () => {
    const { default: useDashboardStore } = await import('./useDashboardStore');

    const filteredCampaignData = {
      summary: campaignData.summary,
      trend: [],
      rows: [
        {
          id: 'cmp_meta',
          name: 'Awareness Boost',
          platform: 'Meta',
          status: 'Active',
          parish: 'Kingston',
          spend: 80,
          impressions: 120,
          clicks: 20,
          conversions: 2,
          roas: 1.8,
        },
        {
          id: 'cmp_search',
          name: 'Search Capture',
          platform: 'Google Ads',
          status: 'Active',
          parish: 'St James',
          spend: 140,
          impressions: 320,
          clicks: 45,
          conversions: 5,
          roas: 2.6,
        },
      ],
    };

    const filteredCreativeData = [
      {
        id: 'cr_meta',
        name: 'Meta Creative',
        campaignId: 'cmp_meta',
        campaignName: 'Awareness Boost',
        platform: 'Meta',
        parish: 'Kingston',
        spend: 35,
        impressions: 90,
        clicks: 8,
        conversions: 1,
        roas: 1.4,
      },
      {
        id: 'cr_search',
        name: 'Search Creative',
        campaignId: 'cmp_search',
        campaignName: 'Search Capture',
        platform: 'Google Ads',
        parish: 'St James',
        spend: 60,
        impressions: 140,
        clicks: 18,
        conversions: 3,
        roas: 2.1,
      },
    ];

    const filteredBudgetData = [
      {
        id: 'budget_meta',
        campaignName: 'Awareness Boost',
        platform: 'Meta',
        parishes: ['Kingston'],
        monthlyBudget: 200,
        spendToDate: 80,
        projectedSpend: 190,
        pacingPercent: 0.95,
      },
      {
        id: 'budget_search',
        campaignName: 'Search Capture',
        platform: 'Google Ads',
        parishes: ['St James'],
        monthlyBudget: 320,
        spendToDate: 140,
        projectedSpend: 330,
        pacingPercent: 1.02,
      },
    ];

    useDashboardStore.setState((state) => ({
      ...state,
      campaign: { status: 'loaded', data: filteredCampaignData, error: undefined },
      creative: { status: 'loaded', data: filteredCreativeData, error: undefined },
      budget: { status: 'loaded', data: filteredBudgetData, error: undefined },
    }));

    useDashboardStore.getState().setFilters({
      dateRange: '7d',
      customRange: { start: '2024-08-01', end: '2024-08-07' },
      channels: ['Google Ads'],
      campaignQuery: 'Search',
    });

    const campaignRows = useDashboardStore.getState().getCampaignRowsForSelectedParish();
    expect(campaignRows).toHaveLength(1);
    expect(campaignRows[0]?.id).toBe('cmp_search');

    const creativeRows = useDashboardStore.getState().getCreativeRowsForSelectedParish();
    expect(creativeRows).toHaveLength(1);
    expect(creativeRows[0]?.id).toBe('cr_search');

    const budgetRows = useDashboardStore.getState().getBudgetRowsForSelectedParish();
    expect(budgetRows).toHaveLength(1);
    expect(budgetRows[0]?.id).toBe('budget_search');
  });

  it('appends filter query params when requesting combined metrics', async () => {
    vi.stubEnv('VITE_MOCK_MODE', 'false');

    const snapshotResponse = {
      metrics: {
        campaign_metrics: campaignData,
        creative_metrics: creativeData,
        budget_metrics: budgetData,
        parish_metrics: parishData,
      },
      tenant_id: 'tenant-xyz',
      generated_at: '2024-09-05T00:00:00Z',
    } satisfies Record<string, unknown>;

    const fetchMock = vi
      .fn<(url: RequestInfo | URL) => Promise<Response>>()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(snapshotResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      );

    globalThis.fetch = fetchMock as typeof globalThis.fetch;

    const { default: useDashboardStore } = await import('./useDashboardStore');

    useDashboardStore.getState().setFilters({
      dateRange: 'custom',
      customRange: { start: '2024-08-01', end: '2024-08-31' },
      channels: ['Meta Ads', 'Google Ads'],
      campaignQuery: 'Kingston',
    });

    await useDashboardStore.getState().loadAll('tenant-xyz', { force: true });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const requestUrl = fetchMock.mock.calls[0]?.[0];
    const serializedUrl = typeof requestUrl === 'string' ? requestUrl : String(requestUrl);
    const query = serializedUrl.split('?')[1] ?? '';
    const params = new URLSearchParams(query);

    expect(params.get('start_date')).toBe('2024-08-01');
    expect(params.get('end_date')).toBe('2024-08-31');
    expect(params.get('channels')).toBe('meta,google_ads');
    expect(params.get('campaign')).toBe('Kingston');
  });

  it('flags API errors without discarding previous data', async () => {
    const fetchMock = vi.fn((url: RequestInfo | URL) => {
      if (
        typeof url === 'string' &&
        (url.endsWith('/sample_campaign_performance.json') ||
          url.includes('/analytics/campaign-performance/'))
      ) {
        return Promise.resolve(
          new Response(JSON.stringify({ detail: 'oops' }), {
            status: 500,
            headers: { 'Content-Type': 'application/json' },
          }),
        );
      }
      if (
        typeof url === 'string' &&
        (url.endsWith('/sample_creative_performance.json') ||
          url.includes('/analytics/creative-performance/'))
      ) {
        return Promise.resolve(
          new Response(JSON.stringify(creativeData), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        );
      }
      if (
        typeof url === 'string' &&
        (url.endsWith('/sample_budget_pacing.json') || url.includes('/analytics/budget-pacing/'))
      ) {
        return Promise.resolve(
          new Response(JSON.stringify(budgetData), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        );
      }
      if (
        typeof url === 'string' &&
        (url.endsWith('/sample_parish_aggregates.json') ||
          url.includes('/analytics/parish-performance/'))
      ) {
        return Promise.resolve(
          new Response(JSON.stringify(parishData), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        );
      }
      return Promise.reject(new Error(`Unhandled fetch: ${String(url)}`));
    });
    globalThis.fetch = fetchMock as typeof globalThis.fetch;

    const { default: useDashboardStore } = await import('./useDashboardStore');

    await useDashboardStore.getState().loadAll();

    expect(useDashboardStore.getState().campaign.status).toBe('error');
    expect(useDashboardStore.getState().creative.status).toBe('loaded');
  });

  it('appends the demo tenant option when requesting curated datasets', async () => {
    vi.stubEnv('VITE_MOCK_MODE', 'false');

    const { useDatasetStore } = await import('./useDatasetStore');
    useDatasetStore.setState({
      mode: 'dummy',
      adapters: ['demo'],
      status: 'loaded',
      error: undefined,
      source: 'demo',
      demoTenants: [
        { id: 'bank-of-jamaica', label: 'Bank of Jamaica' },
        { id: 'grace-kennedy', label: 'GraceKennedy' },
      ],
      demoTenantId: 'grace-kennedy',
    });

    const snapshotResponse = {
      campaign: campaignData,
      creative: creativeData,
      budget: budgetData,
      parish: parishData,
      tenant_id: 'grace-kennedy',
    };

    const fetchMock = vi
      .fn<(url: RequestInfo | URL) => Promise<Response>>()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(snapshotResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      );

    globalThis.fetch = fetchMock as typeof globalThis.fetch;

    const { default: useDashboardStore } = await import('./useDashboardStore');

    await useDashboardStore.getState().loadAll('tenant-xyz', { force: true });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const requestUrl = fetchMock.mock.calls[0]?.[0];
    const serializedUrl = typeof requestUrl === 'string' ? requestUrl : String(requestUrl);
    expect(serializedUrl).toContain('source=demo');
    expect(serializedUrl).toContain('demo_tenant=grace-kennedy');

    const state = useDashboardStore.getState();
    expect(state.campaign.status).toBe('loaded');
    expect(state.campaign.data?.summary.currency).toBe('JMD');
    expect(state.activeTenantId).toBe('grace-kennedy');
  });
});
