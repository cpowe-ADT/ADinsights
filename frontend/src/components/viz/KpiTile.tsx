import { memo, useMemo, type ReactNode } from 'react';

import { formatCompactNumber, formatCurrency, formatPercent } from '../../lib/formatNumber';

export type KpiFormat = 'currency' | 'number' | 'percent' | 'rate';

export type KpiTileProps = {
  label: string;
  /** Raw value. `null` renders the no-data dash with a descriptive aria-label. */
  value: number | null;
  format?: KpiFormat;
  currency?: string;
  /**
   * Percent change vs. prior period, expressed as a decimal (e.g. 0.12 = +12%).
   * Direction is inferred from sign. Pass `null` to hide.
   */
  change?: number | null;
  /** Sparkline trend points. At least two finite numbers required to render. */
  trend?: number[];
  hint?: string;
  tooltip?: string;
  /** Renders the loading skeleton variant. */
  isLoading?: boolean;
  /** Dims the tile — used when a global filter excludes this card. */
  isFaded?: boolean;
  /** Stable identifier for analytics / tests / future i18n. */
  reasonCode?: string;
  /** Optional right-aligned status badge. */
  badge?: ReactNode;
  className?: string;
};

const NO_DATA = '—';

const isFiniteNumber = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value);

const clampTrend = (trend: number[] | undefined): number[] => {
  if (!trend) {
    return [];
  }
  return trend.filter(isFiniteNumber);
};

const formatValue = (
  value: number | null,
  format: KpiFormat,
  currency: string | undefined,
): string => {
  if (value === null || !isFiniteNumber(value)) {
    return NO_DATA;
  }

  switch (format) {
    case 'currency':
      return formatCurrency(value, currency ?? 'JMD');
    case 'percent':
      // Percent values come in as decimals (0.12 = 12%). `formatPercent` uses
      // Intl percent-style which multiplies by 100 internally.
      return formatPercent(value);
    case 'rate':
      // CTR / frequency style — already a decimal or a small ratio. Render as
      // a percent if < 1, else as a compact number.
      return Math.abs(value) < 1 ? formatPercent(value) : formatCompactNumber(value);
    case 'number':
    default:
      return formatCompactNumber(value);
  }
};

const formatChangeLabel = (change: number): string => {
  const abs = Math.abs(change);
  return formatPercent(abs);
};

const KpiTile = ({
  label,
  value,
  format = 'number',
  currency,
  change,
  trend,
  hint,
  tooltip,
  isLoading,
  isFaded,
  reasonCode,
  badge,
  className,
}: KpiTileProps) => {
  const sanitizedTrend = useMemo(() => clampTrend(trend), [trend]);

  const sparkline = useMemo(() => {
    if (sanitizedTrend.length < 2) {
      return undefined;
    }

    const min = Math.min(...sanitizedTrend);
    const max = Math.max(...sanitizedTrend);
    const range = max - min || 1;

    const points = sanitizedTrend.map((point, index) => {
      const x = (index / (sanitizedTrend.length - 1)) * 100;
      const y = 32 - ((point - min) / range) * 28 - 2;
      return { x: Number(x.toFixed(2)), y: Number(y.toFixed(2)) };
    });

    const linePath = points
      .map((point, index) => `${index === 0 ? 'M' : 'L'}${point.x},${point.y}`)
      .join(' ');
    const areaPath = `${linePath} L100,32 L0,32 Z`;

    return { linePath, areaPath };
  }, [sanitizedTrend]);

  const displayValue = formatValue(value, format, currency);
  const hasValue = value !== null && isFiniteNumber(value);

  const direction: 'up' | 'down' | 'flat' =
    change === null || change === undefined || !isFiniteNumber(change) || change === 0
      ? 'flat'
      : change > 0
        ? 'up'
        : 'down';

  const tone = direction === 'down' ? 'negative' : direction === 'up' ? 'positive' : 'neutral';

  const changeLabel =
    change !== null && change !== undefined && isFiniteNumber(change)
      ? formatChangeLabel(change)
      : undefined;

  // Delta narration — never rely on color alone. The arrow + aria-label convey
  // direction for screen readers and non-color-sensitive users.
  const deltaAriaLabel =
    changeLabel !== undefined
      ? direction === 'up'
        ? `increased by ${changeLabel}`
        : direction === 'down'
          ? `decreased by ${changeLabel}`
          : `unchanged`
      : undefined;

  const valueAriaLabel = hasValue ? undefined : `${label}: no data`;

  const mergedClassName = [
    'metric-card',
    'kpi-tile',
    isFaded ? 'kpi-tile--faded' : null,
    isLoading ? 'kpi-tile--loading' : null,
    className,
  ]
    .filter(Boolean)
    .join(' ');

  if (isLoading) {
    return (
      <article
        className={mergedClassName}
        aria-busy="true"
        aria-live="polite"
        data-reason-code={reasonCode}
      >
        <div className="kpi-tile__skeleton" role="presentation" aria-hidden="true">
          <span className="kpi-tile__skeleton-label" />
          <span className="kpi-tile__skeleton-value" />
          <span className="kpi-tile__skeleton-spark" />
        </div>
      </article>
    );
  }

  const deltaNode =
    changeLabel !== undefined ? (
      <span
        className={`metric-card__delta metric-card__delta--${tone}`}
        aria-label={deltaAriaLabel}
      >
        <span aria-hidden="true" className="metric-card__delta-icon">
          {direction === 'down' ? '▼' : direction === 'up' ? '▲' : '–'}
        </span>
        {changeLabel}
      </span>
    ) : null;

  return (
    <article className={mergedClassName} data-reason-code={reasonCode}>
      <header className="metric-card__header">
        <p className="metric-card__label" title={tooltip ?? undefined}>
          {label}
        </p>
        {badge ? <span className="metric-card__badge">{badge}</span> : null}
      </header>

      <div className="metric-card__value-row">
        <span className="metric-card__value" aria-label={valueAriaLabel}>
          {displayValue}
        </span>
        {!sparkline && deltaNode}
      </div>

      {sparkline ? (
        <div className="metric-card__sparkline" role="img" aria-label={`${label} trend`}>
          <svg viewBox="0 0 100 32" preserveAspectRatio="none" aria-hidden="true">
            <path className="metric-card__sparkline-area" d={sparkline.areaPath} />
            <path className="metric-card__sparkline-line" d={sparkline.linePath} />
          </svg>
          {deltaNode}
        </div>
      ) : null}

      {hint ? <p className="metric-card__hint">{hint}</p> : null}
    </article>
  );
};

export default memo(KpiTile);
