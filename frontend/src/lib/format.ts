const integerFormatter = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
const relativeFormatter = new Intl.RelativeTimeFormat('en-US', { numeric: 'auto' });

export function formatNumber(value: number | undefined | null): string {
  return integerFormatter.format(Number.isFinite(Number(value)) ? Number(value) : 0);
}

export function formatCurrency(
  value: number | undefined | null,
  currency = 'USD',
  maximumFractionDigits = 0,
): string {
  const formatter = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    maximumFractionDigits,
  });
  return formatter.format(Number.isFinite(Number(value)) ? Number(value) : 0);
}

export function formatPercent(value: number | undefined | null, maximumFractionDigits = 1): string {
  const formatter = new Intl.NumberFormat('en-US', {
    style: 'percent',
    maximumFractionDigits,
  });
  return formatter.format(Number.isFinite(Number(value)) ? Number(value) : 0);
}

export function formatRatio(value: number | undefined | null, digits = 2): string {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return (0).toFixed(digits);
  }
  return numeric.toFixed(digits);
}

function normaliseDate(value: string | number | Date | undefined | null): Date | null {
  if (value instanceof Date) {
    return Number.isFinite(value.getTime()) ? value : null;
  }
  if (typeof value === 'string' || typeof value === 'number') {
    const parsed = new Date(value);
    return Number.isFinite(parsed.getTime()) ? parsed : null;
  }
  return null;
}

export function formatRelativeTime(
  value: string | number | Date | undefined | null,
  now: Date = new Date(),
): string | null {
  const target = normaliseDate(value);
  if (!target) {
    return null;
  }
  const diffMs = target.getTime() - now.getTime();
  const minutes = Math.round(diffMs / 60000);
  if (Math.abs(minutes) < 60) {
    return relativeFormatter.format(minutes, 'minute');
  }
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) {
    return relativeFormatter.format(hours, 'hour');
  }
  const days = Math.round(hours / 24);
  return relativeFormatter.format(days, 'day');
}

export function isTimestampStale(
  value: string | undefined | null,
  thresholdMinutes = 60,
  now: Date = new Date(),
): boolean {
  const target = normaliseDate(value);
  if (!target) {
    return true;
  }
  const diffMinutes = (now.getTime() - target.getTime()) / 60000;
  return diffMinutes > thresholdMinutes;
}

export function formatAbsoluteTime(
  value: string | number | Date | undefined | null,
  timeZone = 'America/Jamaica',
): string | null {
  const target = normaliseDate(value);
  if (!target) {
    return null;
  }
  try {
    const formatter = new Intl.DateTimeFormat('en-JM', {
      dateStyle: 'medium',
      timeStyle: 'short',
      timeZone,
    });
    return formatter.format(target);
  } catch {
    return target.toISOString();
  }
}
