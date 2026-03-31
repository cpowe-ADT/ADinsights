import { describe, expect, it, vi } from 'vitest';

import {
  buildFilterUrlParams,
  createDefaultFilterState,
  parseFilterQueryParams,
  resolveFilterRange,
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
});
