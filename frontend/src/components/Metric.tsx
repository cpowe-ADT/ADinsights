import { memo, useMemo } from 'react';

type DeltaDirection = 'up' | 'down' | 'flat';

export type MetricBadge = 'New' | 'Paused' | 'Limited data';

type MetricProps = {
  label: string;
  value: string | number;
  delta?: string;
  deltaDirection?: DeltaDirection;
  hint?: string;
  trend?: number[];
  badge?: MetricBadge;
  className?: string;
};

const clampTrend = (trend?: number[]) => {
  if (!trend) {
    return [];
  }

  return trend.filter((point) => Number.isFinite(point));
};

const Metric = ({
  label,
  value,
  delta,
  deltaDirection = 'flat',
  hint,
  trend,
  badge,
  className,
}: MetricProps) => {
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

  const tone =
    deltaDirection === 'down' ? 'negative' : deltaDirection === 'up' ? 'positive' : 'neutral';

  const mergedClassName = ['metric-card', className].filter(Boolean).join(' ');

  return (
    <article className={mergedClassName}>
      <header className="metric-card__header">
        <p className="metric-card__label">{label}</p>
        {badge ? (
          <span
            className={`metric-card__badge metric-card__badge--${badge.replace(/\s+/g, '-').toLowerCase()}`}
          >
            {badge}
          </span>
        ) : null}
      </header>

      <div className="metric-card__value-row">
        <span className="metric-card__value">{value}</span>
        {!sparkline && delta ? (
          <span className={`metric-card__delta metric-card__delta--${tone}`}>
            <span aria-hidden="true" className="metric-card__delta-icon">
              {deltaDirection === 'down' ? '▼' : deltaDirection === 'up' ? '▲' : '–'}
            </span>
            {delta}
          </span>
        ) : null}
      </div>

      {sparkline ? (
        <div className="metric-card__sparkline" role="img" aria-label={`${label} trend`}>
          <svg viewBox="0 0 100 32" preserveAspectRatio="none" aria-hidden="true">
            <path className="metric-card__sparkline-area" d={sparkline.areaPath} />
            <path className="metric-card__sparkline-line" d={sparkline.linePath} />
          </svg>
          {delta ? (
            <span className={`metric-card__delta metric-card__delta--${tone}`}>
              <span aria-hidden="true" className="metric-card__delta-icon">
                {deltaDirection === 'down' ? '▼' : deltaDirection === 'up' ? '▲' : '–'}
              </span>
              {delta}
            </span>
          ) : null}
        </div>
      ) : null}

      {hint ? <p className="metric-card__hint">{hint}</p> : null}
    </article>
  );
};

export default memo(Metric);
