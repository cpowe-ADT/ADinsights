import { describe, expect, it } from 'vitest';

import {
  formatAbsoluteTime,
  formatCurrency,
  formatNumber,
  formatPercent,
  formatRatio,
  formatRelativeTime,
  isTimestampStale,
} from './format';

describe('formatNumber', () => {
  it('formats integers', () => {
    expect(formatNumber(1234)).toBe('1,234');
  });

  it('returns 0 for null', () => {
    expect(formatNumber(null)).toBe('0');
  });

  it('returns 0 for undefined', () => {
    expect(formatNumber(undefined)).toBe('0');
  });
});

describe('formatCurrency', () => {
  it('formats USD', () => {
    expect(formatCurrency(1000, 'USD')).toBe('$1,000');
  });

  it('returns $0 for null', () => {
    expect(formatCurrency(null, 'USD')).toBe('$0');
  });

  it('supports fraction digits', () => {
    const result = formatCurrency(9.99, 'USD', 2);
    expect(result).toContain('9.99');
  });
});

describe('formatPercent', () => {
  it('formats a decimal as percent', () => {
    expect(formatPercent(0.5)).toContain('50');
  });

  it('returns 0% for null', () => {
    expect(formatPercent(null)).toBe('0%');
  });
});

describe('formatRatio', () => {
  it('formats a ratio with fixed digits', () => {
    expect(formatRatio(3.14159, 2)).toBe('3.14');
  });

  it('returns 0.00 for null', () => {
    expect(formatRatio(null, 2)).toBe('0.00');
  });

  it('returns 0.00 for NaN', () => {
    expect(formatRatio(NaN, 2)).toBe('0.00');
  });
});

describe('formatRelativeTime', () => {
  it('returns null for invalid input', () => {
    expect(formatRelativeTime(null)).toBeNull();
    expect(formatRelativeTime(undefined)).toBeNull();
    expect(formatRelativeTime('not-a-date')).toBeNull();
  });

  it('formats minutes ago', () => {
    const now = new Date('2026-04-10T12:00:00Z');
    const target = new Date('2026-04-10T11:30:00Z');
    const result = formatRelativeTime(target, now);
    expect(result).toBeTruthy();
    expect(result).toContain('30');
  });
});

describe('isTimestampStale', () => {
  it('returns true for null', () => {
    expect(isTimestampStale(null)).toBe(true);
  });

  it('returns false for recent timestamp', () => {
    const now = new Date('2026-04-10T12:00:00Z');
    expect(isTimestampStale('2026-04-10T11:30:00Z', 60, now)).toBe(false);
  });

  it('returns true for old timestamp', () => {
    const now = new Date('2026-04-10T12:00:00Z');
    expect(isTimestampStale('2026-04-10T10:00:00Z', 60, now)).toBe(true);
  });
});

describe('formatAbsoluteTime', () => {
  it('returns null for null input', () => {
    expect(formatAbsoluteTime(null)).toBeNull();
  });

  it('formats a valid date', () => {
    const result = formatAbsoluteTime('2026-04-10T12:00:00Z', 'America/Jamaica');
    expect(result).toBeTruthy();
  });
});
