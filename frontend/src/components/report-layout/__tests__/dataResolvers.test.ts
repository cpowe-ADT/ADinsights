import { describe, expect, it } from 'vitest';

import { createStoreResolver, resolveStoreData } from '../dataResolvers';
import type { DashboardWidget } from '../layoutSchema';

const widget = (over: Partial<DashboardWidget>): DashboardWidget => ({
  id: 'x',
  type: 'kpi',
  x: 1,
  y: 1,
  w: 1,
  h: 1,
  ...over,
});

const data = {
  summary: { totalSpend: 478000, totalClicks: 10950, currency: 'JMD' },
  parish: [
    { parish: 'Kingston', spend: 478000, clicks: 10950 },
    { parish: 'St James', spend: 415000, clicks: 10120 },
  ],
};

describe('resolveStoreData', () => {
  it('resolves summary.<field> to a number, null for non-numbers/missing', () => {
    expect(resolveStoreData(widget({ dataKey: 'summary.totalSpend' }), data)).toBe(478000);
    expect(resolveStoreData(widget({ dataKey: 'summary.currency' }), data)).toBeNull();
    expect(resolveStoreData(widget({ dataKey: 'summary.missing' }), data)).toBeNull();
  });

  it('maps parish.<metric> to {label, value} chart data', () => {
    expect(resolveStoreData(widget({ type: 'bar', dataKey: 'parish.spend' }), data)).toEqual([
      { label: 'Kingston', value: 478000 },
      { label: 'St James', value: 415000 },
    ]);
  });

  it('returns raw rows for parish.rows', () => {
    expect(resolveStoreData(widget({ type: 'table', dataKey: 'parish.rows' }), data)).toEqual(
      data.parish,
    );
  });

  it('falls back to inline data when there is no dataKey', () => {
    expect(resolveStoreData(widget({ data: 42 }), data)).toBe(42);
  });

  it('createStoreResolver binds a snapshot', () => {
    const resolve = createStoreResolver(data);
    expect(resolve(widget({ dataKey: 'summary.totalClicks' }))).toBe(10950);
  });
});
