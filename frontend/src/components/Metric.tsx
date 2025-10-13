import { useMemo } from "react";

export type MetricDeltaDirection = "up" | "down" | "neutral";
export type MetricBadge = "New" | "Paused" | "Limited data";

export interface MetricProps {
  label: string;
  value: string;
  delta?: string;
  deltaDirection?: MetricDeltaDirection;
  hint?: string;
  trend?: number[];
  badge?: MetricBadge;
}

interface SparklinePath {
  line: string;
  area: string;
}

const SPARKLINE_WIDTH = 104;
const SPARKLINE_HEIGHT = 36;

function buildSparkline(values: number[]): SparklinePath | undefined {
  if (!values.length) {
    return undefined;
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const step = values.length > 1 ? SPARKLINE_WIDTH / (values.length - 1) : SPARKLINE_WIDTH;

  const points = values.map((value, index) => {
    const normalized = (value - min) / range;
    const y = SPARKLINE_HEIGHT - normalized * SPARKLINE_HEIGHT;
    const x = index * step;
    return {
      x: Number.isFinite(x) ? Number(x.toFixed(2)) : 0,
      y: Number.isFinite(y) ? Number(y.toFixed(2)) : SPARKLINE_HEIGHT,
    };
  });

  const line = points
    .map((point, index) => `${index === 0 ? "M" : "L"}${point.x},${point.y}`)
    .join(" ");

  const area = [`M0,${SPARKLINE_HEIGHT}`, ...points.map((point) => `L${point.x},${point.y}`), `L${SPARKLINE_WIDTH},${SPARKLINE_HEIGHT}`, "Z"].join(" ");

  return { line, area };
}

const Metric = ({
  label,
  value,
  delta,
  deltaDirection = "neutral",
  hint,
  trend,
  badge,
}: MetricProps) => {
  const sparkline = useMemo(() => {
    if (!trend || trend.length < 2) {
      return undefined;
    }

    return buildSparkline(trend);
  }, [trend]);

  const arrow = deltaDirection === "up" ? "▲" : deltaDirection === "down" ? "▼" : "—";
  const trendClass = sparkline ? ` metric-card__sparkline--${deltaDirection}` : "";
  const deltaClass = `metric-card__delta metric-card__delta--${deltaDirection}`;

  return (
    <div className="metric-card">
      <header className="metric-card__header">
        <span className="metric-card__label" title={label}>
          {label}
        </span>
        {badge ? (
          <span className="metric-card__meta">
            <span className={`metric-card__badge metric-card__badge--${badge.replace(/\s+/g, "-").toLowerCase()}`}>
              {badge}
            </span>
          </span>
        ) : null}
      </header>
      <div className="metric-card__body">
        <span className="metric-card__value">{value}</span>
        {sparkline ? (
          <svg
            className={`metric-card__sparkline${trendClass}`}
            viewBox={`0 0 ${SPARKLINE_WIDTH} ${SPARKLINE_HEIGHT}`}
            role="img"
            aria-hidden="true"
            focusable="false"
          >
            <path className="metric-card__sparkline-area" d={sparkline.area} />
            <path className="metric-card__sparkline-line" d={sparkline.line} />
          </svg>
        ) : delta ? (
          <span className={deltaClass} aria-label={deltaDirection !== "neutral" ? `${deltaDirection} ${delta}` : delta}>
            <span className="metric-card__delta-icon" aria-hidden="true">
              {arrow}
            </span>
            <span className="metric-card__delta-value">{delta}</span>
          </span>
        ) : null}
      </div>
      {hint ? <p className="metric-card__hint">{hint}</p> : null}
    </div>
  );
};

export default Metric;
