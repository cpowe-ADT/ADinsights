const DEFAULT_LOCALE = 'en-JM';

const isFiniteNumber = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value);

const coerceNumber = (value: unknown): number | null => {
  if (isFiniteNumber(value)) {
    return value;
  }

  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
};

export function formatCompactNumber(
  value: unknown,
  maximumFractionDigits = 1,
  locale = DEFAULT_LOCALE,
): string {
  const numeric = coerceNumber(value);
  if (numeric === null) {
    return '—';
  }

  const formatter = new Intl.NumberFormat(locale, {
    notation: 'compact',
    maximumFractionDigits,
  });

  return formatter.format(numeric);
}

export function formatCurrency(
  value: unknown,
  currency = 'JMD',
  maximumFractionDigits = 0,
  locale = DEFAULT_LOCALE,
): string {
  const numeric = coerceNumber(value);
  if (numeric === null) {
    return '—';
  }

  const formatter = new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    maximumFractionDigits,
  });

  return formatter.format(numeric);
}

export function formatPercent(
  value: unknown,
  maximumFractionDigits = 1,
  locale = DEFAULT_LOCALE,
): string {
  const numeric = coerceNumber(value);
  if (numeric === null) {
    return '—';
  }

  const formatter = new Intl.NumberFormat(locale, {
    style: 'percent',
    maximumFractionDigits,
  });

  return formatter.format(numeric);
}

export type NumericFormatter = (value: unknown) => string;

export type ValueFormatterKey = keyof typeof valueFormatters;

export const valueFormatters = {
  number: (value: unknown) => formatCompactNumber(value),
  currency: (value: unknown, currency = 'JMD') => formatCurrency(value, currency),
  percent: (value: unknown) => formatPercent(value),
};

export const formatNumber = formatCompactNumber;
