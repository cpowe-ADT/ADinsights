import { describe, expect, it } from 'vitest';

import { clampMove, clampResize, columnPixels, nextFreeRow, pxToUnits } from '../gridMath';
import type { DashboardWidget } from '../layoutSchema';

const widget = (over: Partial<DashboardWidget>): DashboardWidget => ({
  id: 'w',
  type: 'kpi',
  x: 1,
  y: 1,
  w: 3,
  h: 2,
  ...over,
});

describe('columnPixels', () => {
  it('returns 0 for a zero-width or zero-column container', () => {
    expect(columnPixels(0, 12, 16)).toBe(0);
    expect(columnPixels(1200, 0, 16)).toBe(0);
  });
  it('divides usable width across columns', () => {
    // (1200 + 16) / 12 ≈ 101.33
    expect(columnPixels(1200, 12, 16)).toBeCloseTo(101.33, 1);
  });
});

describe('pxToUnits', () => {
  it('snaps a pixel delta to the nearest grid unit', () => {
    expect(pxToUnits(0, 100)).toBe(0);
    expect(pxToUnits(140, 100)).toBe(1);
    expect(pxToUnits(160, 100)).toBe(2);
    expect(pxToUnits(-160, 100)).toBe(-2);
  });
  it('guards against a zero/invalid cell size', () => {
    expect(pxToUnits(50, 0)).toBe(0);
    expect(pxToUnits(50, Number.NaN)).toBe(0);
  });
});

describe('clampMove', () => {
  it('keeps the widget inside the grid', () => {
    const w = widget({ x: 5, y: 5, w: 3, h: 2 });
    expect(clampMove(w, 2, 1, 12)).toEqual({ x: 7, y: 6 });
    expect(clampMove(w, 99, -99, 12)).toEqual({ x: 10, y: 1 }); // x clamped to cols-w+1; y>=1
    expect(clampMove(w, -99, 3, 12)).toEqual({ x: 1, y: 8 }); // x>=1
  });
});

describe('clampResize', () => {
  it('keeps size >= 1 and within the column count', () => {
    const w = widget({ type: 'bar', x: 3, y: 1, w: 4, h: 3 });
    expect(clampResize(w, 2, 1, 12)).toEqual({ w: 6, h: 4 });
    expect(clampResize(w, -99, -99, 12)).toEqual({ w: 1, h: 1 });
    expect(clampResize(w, 99, 0, 12)).toEqual({ w: 10, h: 3 }); // maxW = cols - x + 1 = 10
  });
});

describe('nextFreeRow', () => {
  it('returns the first row below every widget', () => {
    expect(
      nextFreeRow([
        widget({ x: 1, y: 1, w: 3, h: 2 }),
        widget({ x: 1, y: 3, w: 4, h: 4 }),
      ]),
    ).toBe(7);
    expect(nextFreeRow([])).toBe(1);
  });
});
