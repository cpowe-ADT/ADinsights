import { useMemo } from 'react';
import type { ComponentType } from 'react';
import { PolarAngleAxis, RadialBar, RadialBarChart, ResponsiveContainer } from 'recharts';

import { chartPalette } from '../../styles/chartTheme';
import EmptyState from '../EmptyState';

import ChartSkeleton from './ChartSkeleton';
import VizEmptyIcon from './VizEmptyIcon';

export type GaugeVariant = 'ok' | 'warning' | 'danger';

export interface GaugeRingProps {
  /** Current value (e.g. pacing_pct, 0..max). */
  value: number;
  /** Domain max (default 1.2 — 120% pacing). */
  max?: number;
  /** Visible label rendered above the gauge (e.g. "Pacing"). */
  label: string;
  /** Threshold zone — drives color + hatch overlay (non-color encoding). */
  variant?: GaugeVariant;
  /** Chart height in px (default 220). */
  height?: number;
  /** Renders a shimmer placeholder. */
  isLoading?: boolean;
  /** Reason forwarded to <EmptyState>. Rendered when value is null/NaN. */
  emptyReasonCode?: string;
  /** Required accessible label used by role="meter" + role="img". */
  ariaLabel: string;
  /** Optional override for aria-valuetext (default formats percent). */
  valueText?: string;
  /** Optional unit suffix for the rendered center label (default "%"). */
  unit?: string;
}

/** Derive a gauge variant from a 0..max value with default pacing thresholds. */
export function derivePacingVariant(
  value: number,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars -- kept for API symmetry with the gauge domain; thresholds are hard-coded to pacing semantics (0.8/1.1) which are independent of max.
  max: number = 1.2,
): GaugeVariant {
  if (!Number.isFinite(value) || value < 0) return 'danger';
  if (value < 0.8) return 'warning';
  if (value > 1.1) return 'danger';
  return 'ok';
}

const VARIANT_COLOR: Record<GaugeVariant, string> = {
  // Avoid chartPalette[1] (orange) at low-contrast states per S1 §10.10.
  ok: chartPalette[3], // green
  warning: chartPalette[2], // cyan (not orange)
  danger: chartPalette[5], // red
};

/**
 * Tick notches at 0, 0.4, 0.8 (on-track lower), 1.1 (overspend), max.
 * This is the non-color threshold encoding required for a11y.
 */
const DEFAULT_TICKS = [0, 0.4, 0.8, 1.1] as const;

const polarToCartesian = (cx: number, cy: number, r: number, angleDeg: number) => {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
};

interface TickMarksProps {
  cx: number;
  cy: number;
  innerRadius: number;
  outerRadius: number;
  max: number;
  ticks: readonly number[];
}

const TickMarks = ({ cx, cy, innerRadius, outerRadius, max, ticks }: TickMarksProps) => (
  <g aria-hidden="true">
    {ticks.map((t) => {
      // 180° semi-circle: 0 at left (180°), max at right (360°). Use that mapping
      // so a growing needle sweeps visually left-to-right.
      const ratio = Math.min(1, Math.max(0, t / max));
      const angleDeg = 180 + ratio * 180;
      const inner = polarToCartesian(cx, cy, innerRadius - 2, angleDeg);
      const outer = polarToCartesian(cx, cy, outerRadius + 4, angleDeg);
      return (
        <line
          key={t}
          x1={inner.x}
          y1={inner.y}
          x2={outer.x}
          y2={outer.y}
          stroke="#0f172a"
          strokeOpacity={0.55}
          strokeWidth={1.5}
        />
      );
    })}
  </g>
);

/**
 * GaugeRing — radial-bar gauge used for pacing / percent-of-budget
 * displays. Declares `role="meter"` with `aria-valuenow/min/max/text` so
 * assistive tech announces the current value correctly. Threshold zones
 * are encoded via tick notches in addition to color so the viz is not
 * color-only (WCAG 1.4.1).
 */
const GaugeRing = ({
  value,
  max = 1.2,
  label,
  variant,
  height = 220,
  isLoading = false,
  emptyReasonCode = 'no_pacing_data',
  ariaLabel,
  valueText,
  unit = '%',
}: GaugeRingProps) => {
  const resolvedVariant = variant ?? derivePacingVariant(value, max);
  const clamped = Number.isFinite(value)
    ? Math.min(Math.max(value, 0), max)
    : 0;
  const color = VARIANT_COLOR[resolvedVariant];

  const chartData = useMemo(
    () => [
      {
        name: label,
        value: clamped,
        fill: color,
      },
    ],
    [clamped, color, label],
  );

  const RadialBarChartComponent = RadialBarChart as unknown as ComponentType<
    Record<string, unknown>
  >;
  const RadialBarComponent = RadialBar as unknown as ComponentType<Record<string, unknown>>;
  const PolarAngleAxisComponent = PolarAngleAxis as unknown as ComponentType<
    Record<string, unknown>
  >;

  if (isLoading) {
    return <ChartSkeleton variant="pie" height={height} />;
  }

  if (value == null || !Number.isFinite(value)) {
    return (
      <EmptyState
        icon={<VizEmptyIcon />}
        title="No pacing data"
        message="We could not compute pacing for the selected range."
        reasonCode={emptyReasonCode}
      />
    );
  }

  const percentOfMax = max > 0 ? (clamped / max) * 100 : 0;
  const displayPercent = `${(clamped * 100).toFixed(0)}${unit}`;
  const resolvedValueText = valueText ?? displayPercent;

  // Semi-circle gauge: start 180°, end 0° (sweep counter-clockwise through 180°).
  const startAngle = 180;
  const endAngle = 0;
  const innerRadius = Math.round(height * 0.32);
  const outerRadius = Math.round(height * 0.48);

  return (
    <div
      style={{ width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center' }}
    >
      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text-secondary)' }}>
        {label}
      </div>
      <div
        role="meter"
        aria-label={ariaLabel}
        aria-valuenow={Number(clamped.toFixed(4))}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuetext={resolvedValueText}
        data-variant={resolvedVariant}
        style={{ width: '100%', position: 'relative' }}
      >
        <ResponsiveContainer width="100%" height={height}>
          <RadialBarChartComponent
            cx="50%"
            cy="75%"
            innerRadius={innerRadius}
            outerRadius={outerRadius}
            barSize={Math.max(10, outerRadius - innerRadius)}
            startAngle={startAngle}
            endAngle={endAngle}
            data={chartData}
          >
            <defs>
              <pattern
                id="viz-gauge-hatch"
                patternUnits="userSpaceOnUse"
                width="6"
                height="6"
                patternTransform="rotate(45)"
              >
                <line
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="6"
                  stroke="#0f172a"
                  strokeWidth="1.5"
                  opacity={0.35}
                />
              </pattern>
            </defs>
            <PolarAngleAxisComponent
              type="number"
              domain={[0, max]}
              angleAxisId={0}
              tick={false}
            />
            <RadialBarComponent
              background={{ fill: 'var(--viz-grid, rgba(15, 23, 42, 0.12))' }}
              dataKey="value"
              cornerRadius={6}
              isAnimationActive={false}
            />
          </RadialBarChartComponent>
        </ResponsiveContainer>
        {/* Tick-mark overlay for non-color threshold encoding. Positioned via
            absolute SVG so it survives Recharts' internal layout. */}
        <svg
          aria-hidden="true"
          viewBox={`0 0 200 ${height}`}
          preserveAspectRatio="xMidYMid meet"
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            pointerEvents: 'none',
          }}
        >
          <TickMarks
            cx={100}
            cy={height * 0.75}
            innerRadius={innerRadius}
            outerRadius={outerRadius}
            max={max}
            ticks={DEFAULT_TICKS}
          />
        </svg>
        <div
          aria-hidden="true"
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            pointerEvents: 'none',
            fontWeight: 700,
            fontSize: 22,
            color: 'var(--color-text-primary, #0f172a)',
          }}
        >
          {displayPercent}
        </div>
      </div>
      <table className="sr-only" aria-label={ariaLabel}>
        <caption>{ariaLabel}</caption>
        <thead>
          <tr>
            <th scope="col">Metric</th>
            <th scope="col">Value</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <th scope="row">{label}</th>
            <td>{resolvedValueText}</td>
            <td>{resolvedVariant}</td>
          </tr>
          <tr>
            <th scope="row">Domain</th>
            <td>{`0 – ${max}`}</td>
            <td>—</td>
          </tr>
          <tr>
            <th scope="row">Percent of max</th>
            <td>{`${percentOfMax.toFixed(0)}%`}</td>
            <td>—</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
};

export default GaugeRing;
