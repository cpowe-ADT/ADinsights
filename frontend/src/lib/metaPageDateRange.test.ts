import { describe, expect, it } from 'vitest';

import {
  createMetaPageDefaultCustomRange,
  normalizeMetaPageDatePreset,
  toMetaPageDateParams,
} from './metaPageDateRange';

describe('metaPageDateRange', () => {
  it('normalizes unsupported presets to last_28d', () => {
    expect(normalizeMetaPageDatePreset('last_7d')).toBe('last_7d');
    expect(normalizeMetaPageDatePreset('unexpected')).toBe('last_28d');
  });

  it('includes since/until only for custom presets', () => {
    expect(
      toMetaPageDateParams({
        datePreset: 'last_28d',
        since: '2026-01-01',
        until: '2026-01-28',
      }),
    ).toEqual({ date_preset: 'last_28d' });

    expect(
      toMetaPageDateParams({
        datePreset: 'custom',
        since: '2026-01-01',
        until: '2026-01-28',
      }),
    ).toEqual({
      date_preset: 'custom',
      since: '2026-01-01',
      until: '2026-01-28',
    });
  });

  it('builds default custom range anchored to yesterday in timezone', () => {
    const range = createMetaPageDefaultCustomRange({
      now: new Date('2026-02-21T10:00:00Z'),
      timeZone: 'America/Jamaica',
    });
    expect(range).toEqual({
      since: '2026-01-24',
      until: '2026-02-20',
    });
  });
});
