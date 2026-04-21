import { describe, expect, it, vi } from 'vitest';

import {
  arePlatformArraysEqual,
  buildFilterUrlParams,
  createDefaultFilterState,
  parseFilterQueryParams,
  resolveFilterRange,
  resolveRoutePlatformScope,
  type FilterBarState,
} from './dashboardFilters';

describe('dashboardFilters', () => {
  it('resolves longer trailing ranges from the selected preset', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-03-27T12:00:00Z'));

    const filters: FilterBarState = {
      ...createDefaultFilterState(),
      dateRange: '180d',
    };

    expect(resolveFilterRange(filters)).toEqual({
      start: '2025-09-29',
      end: '2026-03-27',
    });

    vi.useRealTimers();
  });

  it('serializes and parses extended presets through query params', () => {
    const filters: FilterBarState = {
      ...createDefaultFilterState(),
      dateRange: '365d',
      accountId: 'act_2278682008940745',
    };

    const params = new URLSearchParams(buildFilterUrlParams(filters));
    const parsed = parseFilterQueryParams(params, createDefaultFilterState());

    expect(parsed.dateRange).toBe('365d');
    expect(parsed.accountId).toBe('act_2278682008940745');
  });

  it('round-trips clientId and platforms through URL params', () => {
    const filters: FilterBarState = {
      ...createDefaultFilterState(),
      clientId: '11111111-2222-3333-4444-555555555555',
      platforms: ['meta_ads', 'google_ads'],
    };

    const params = new URLSearchParams(buildFilterUrlParams(filters));
    expect(params.get('client_id')).toBe('11111111-2222-3333-4444-555555555555');
    expect(params.get('platforms')).toBe('meta_ads,google_ads');

    const parsed = parseFilterQueryParams(params, createDefaultFilterState());
    expect(parsed.clientId).toBe('11111111-2222-3333-4444-555555555555');
    expect(parsed.platforms).toEqual(['meta_ads', 'google_ads']);
  });

  it('omits empty clientId and platforms from URL params', () => {
    const filters: FilterBarState = createDefaultFilterState();
    const params = new URLSearchParams(buildFilterUrlParams(filters));
    expect(params.get('client_id')).toBeNull();
    expect(params.get('platforms')).toBeNull();
  });
});

// R6: resolveRoutePlatformScope extracted for unit testing
describe('resolveRoutePlatformScope', () => {
  it.each([
    ['/dashboards/meta/accounts', ['meta_ads']],
    ['/dashboards/meta/insights', ['meta_ads']],
    ['/dashboards/meta/campaigns', ['meta_ads']],
    ['/dashboards/meta/pages', ['meta_ads']],
    ['/dashboards/meta/pages/p1/overview', ['meta_ads']],
    ['/dashboards/meta/posts/post123', ['meta_ads']],
    ['/dashboards/google-ads', ['google_ads']],
    ['/dashboards/google-ads/', ['google_ads']],
    ['/dashboards/google-ads/campaigns', ['google_ads']],
    ['/dashboards/google-ads/executive', ['google_ads']],
    ['/dashboards/platforms', null],
    ['/dashboards/campaigns', null],
    ['/dashboards/creatives', null],
    ['/dashboards/budget', null],
    ['/dashboards/audience', null],
    ['/dashboards', null],
    ['/dashboards/data-sources', null],
    ['/dashboards/saved/abc', null],
  ])('resolveRoutePlatformScope(%s) = %j', (pathname, expected) => {
    expect(resolveRoutePlatformScope(pathname)).toEqual(expected);
  });
});

describe('arePlatformArraysEqual', () => {
  it('returns true for identical arrays', () => {
    expect(arePlatformArraysEqual(['meta_ads', 'google_ads'], ['meta_ads', 'google_ads'])).toBe(true);
  });

  it('returns true for same values in different order', () => {
    expect(arePlatformArraysEqual(['google_ads', 'meta_ads'], ['meta_ads', 'google_ads'])).toBe(true);
  });

  it('returns false for different lengths', () => {
    expect(arePlatformArraysEqual(['meta_ads'], ['meta_ads', 'google_ads'])).toBe(false);
  });

  it('returns false for different values', () => {
    expect(arePlatformArraysEqual(['meta_ads'], ['google_ads'])).toBe(false);
  });

  it('returns true for empty arrays', () => {
    expect(arePlatformArraysEqual([], [])).toBe(true);
  });
});
