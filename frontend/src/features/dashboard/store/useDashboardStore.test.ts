import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

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
}

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
]

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
]

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
]

describe('useDashboardStore', () => {
  const originalFetch = globalThis.fetch

  beforeEach(() => {
    vi.resetModules()
    vi.unstubAllEnvs()
    vi.stubEnv('VITE_MOCK_MODE', 'true')
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllEnvs()
    if (originalFetch) {
      globalThis.fetch = originalFetch
    } else {
      Reflect.deleteProperty(globalThis as typeof globalThis & { fetch?: unknown }, 'fetch')
    }
  })

  it('loads dashboard data from the mock endpoints', async () => {
    const fetchMock = vi.fn((url: RequestInfo | URL) => {
      if (typeof url === 'string' && url.endsWith('/sample_campaign_performance.json')) {
        return Promise.resolve(
          new Response(JSON.stringify(campaignData), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        )
      }
      if (typeof url === 'string' && url.endsWith('/sample_creative_performance.json')) {
        return Promise.resolve(
          new Response(JSON.stringify(creativeData), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        )
      }
      if (typeof url === 'string' && url.endsWith('/sample_budget_pacing.json')) {
        return Promise.resolve(
          new Response(JSON.stringify(budgetData), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        )
      }
      if (typeof url === 'string' && url.endsWith('/sample_parish_aggregates.json')) {
        return Promise.resolve(
          new Response(JSON.stringify(parishData), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        )
      }
      return Promise.reject(new Error(`Unhandled fetch: ${String(url)}`))
    })
    globalThis.fetch = fetchMock as typeof globalThis.fetch

    const { default: useDashboardStore } = await import('./useDashboardStore')

    await useDashboardStore.getState().loadAll('tenant-123')

    const state = useDashboardStore.getState()
    expect(state.campaign.data?.rows).toHaveLength(1)
    expect(state.creative.data).toHaveLength(1)
    expect(state.budget.data).toHaveLength(1)
    expect(state.parish.data).toHaveLength(1)
    expect(state.getCampaignRowsForSelectedParish()).toHaveLength(1)
    expect(state.getCachedMetrics('tenant-123')).toBeDefined()
    expect(state.selectedParish).toBeUndefined()
  })

  it('loads aggregated metrics and reuses the tenant cache when mock mode is disabled', async () => {
    vi.stubEnv('VITE_MOCK_MODE', 'false')

    const snapshotResponse = {
      metrics: {
        campaign_metrics: campaignData,
        creative_metrics: creativeData,
        budget_metrics: budgetData,
        parish_metrics: parishData,
      },
      tenant_id: 'tenant-xyz',
      generated_at: '2024-09-05T00:00:00Z',
    } satisfies Record<string, unknown>

    const fetchMock = vi
      .fn<(url: RequestInfo | URL) => Promise<Response>>()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(snapshotResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockRejectedValueOnce(new Error('Service unavailable'))

    globalThis.fetch = fetchMock as typeof globalThis.fetch

    const { default: useDashboardStore } = await import('./useDashboardStore')

    await useDashboardStore.getState().loadAll('tenant-xyz')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const requestUrl = fetchMock.mock.calls[0]?.[0]
    expect(typeof requestUrl === 'string' ? requestUrl : String(requestUrl)).toContain(
      '/api/dashboards/aggregate-snapshot/',
    )

    let state = useDashboardStore.getState()
    expect(state.campaign.status).toBe('loaded')
    expect(state.campaign.data?.rows).toHaveLength(1)
    expect(state.getCampaignRowsForSelectedParish()).toHaveLength(1)
    state.setSelectedParish('Kingston')
    expect(state.getCampaignRowsForSelectedParish()).toHaveLength(1)
    expect(state.getCachedMetrics('tenant-xyz')?.campaign.rows).toHaveLength(1)

    await useDashboardStore.getState().loadAll('tenant-xyz')

    expect(fetchMock).toHaveBeenCalledTimes(1)

    await useDashboardStore.getState().loadAll('tenant-xyz', { force: true })

    expect(fetchMock).toHaveBeenCalledTimes(2)

    state = useDashboardStore.getState()
    expect(state.campaign.status).toBe('error')
    expect(state.campaign.data?.rows).toHaveLength(1)
    expect(state.campaign.error).toContain('Service unavailable')

    await useDashboardStore.getState().loadAll('tenant-xyz')

    expect(fetchMock).toHaveBeenCalledTimes(2)

    state = useDashboardStore.getState()
    expect(state.campaign.status).toBe('loaded')
    expect(state.campaign.data?.rows).toHaveLength(1)
  })

  it('flags API errors without discarding previous data', async () => {
    const fetchMock = vi.fn((url: RequestInfo | URL) => {
      if (typeof url === 'string' && url.endsWith('/sample_campaign_performance.json')) {
        return Promise.resolve(
          new Response(JSON.stringify({ detail: 'oops' }), {
            status: 500,
            headers: { 'Content-Type': 'application/json' },
          }),
        )
      }
      if (typeof url === 'string' && url.endsWith('/sample_creative_performance.json')) {
        return Promise.resolve(
          new Response(JSON.stringify(creativeData), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        )
      }
      if (typeof url === 'string' && url.endsWith('/sample_budget_pacing.json')) {
        return Promise.resolve(
          new Response(JSON.stringify(budgetData), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        )
      }
      if (typeof url === 'string' && url.endsWith('/sample_parish_aggregates.json')) {
        return Promise.resolve(
          new Response(JSON.stringify(parishData), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        )
      }
      return Promise.reject(new Error(`Unhandled fetch: ${String(url)}`))
    })
    globalThis.fetch = fetchMock as typeof globalThis.fetch

    const { default: useDashboardStore } = await import('./useDashboardStore')

    await useDashboardStore.getState().loadAll()

    expect(useDashboardStore.getState().campaign.status).toBe('error')
    expect(useDashboardStore.getState().creative.status).toBe('loaded')
  })
})
