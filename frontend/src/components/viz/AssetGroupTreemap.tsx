import { useMemo } from 'react';
import type { ComponentType, CSSProperties } from 'react';
import { ResponsiveContainer, Tooltip, Treemap } from 'recharts';

import {
  createTooltipProps,
  resolveSeriesColor,
} from '../../styles/chartTheme';
import { formatCompactNumber, formatCurrency } from '../../lib/formatNumber';
import EmptyState from '../EmptyState';

import ChartSkeleton from './ChartSkeleton';
import VizEmptyIcon from './VizEmptyIcon';

export interface AssetGroupTreemapDatum {
  /** Asset group name (also used as the accessible row header). */
  name: string;
  /** Size dimension — usually spend (currency). */
  spend: number;
  /** Color/opacity dimension — ROAS. Clamped to [0, 2] then mapped to 0.3..1.0. */
  roas?: number;
}

export interface AssetGroupTreemapProps {
  data: AssetGroupTreemapDatum[];
  /** Chart height in px (default 320). */
  height?: number;
  /** ISO currency code — formats spend in the sr-only table + tooltip. */
  currency?: string;
  /** Renders a shimmer placeholder. */
  isLoading?: boolean;
  /** Reason forwarded to <EmptyState>. */
  emptyReasonCode?: string;
  /** Required accessible label. */
  ariaLabel: string;
}

const clamp01 = (v: number): number => (v < 0 ? 0 : v > 1 ? 1 : v);

/** Map ROAS ∈ [0, 2+] → opacity ∈ [0.3, 1.0]. Undefined ROAS falls to 0.6. */
export function roasToOpacity(roas: number | undefined): number {
  if (roas == null || !Number.isFinite(roas)) return 0.6;
  const normalized = clamp01(roas / 2);
  return 0.3 + normalized * 0.7;
}

/** Non-color hatch markers for the lowest-ROAS quartile (accessibility). */
const isLowRoas = (roas: number | undefined): boolean => (roas ?? 0) < 0.5;

interface TreemapCellProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  name?: string;
  value?: number;
  roas?: number;
  /** Root color — the single series color for the treemap. */
  rootColor: string;
}

const TreemapCell = ({
  x = 0,
  y = 0,
  width = 0,
  height = 0,
  name = '',
  roas,
  rootColor,
}: TreemapCellProps) => {
  if (width <= 0 || height <= 0) return null;
  const opacity = roasToOpacity(roas);
  const lowRoas = isLowRoas(roas);
  const label = name.length > 18 ? `${name.slice(0, 15)}…` : name;
  const showLabel = width > 60 && height > 28;

  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        fill={lowRoas ? 'url(#viz-treemap-hatch)' : rootColor}
        fillOpacity={lowRoas ? 1 : opacity}
        stroke="var(--color-surface-card, #ffffff)"
        strokeWidth={2}
      />
      {showLabel ? (
        <text
          x={x + 8}
          y={y + 18}
          fontSize={12}
          fill="#0f172a"
          style={{ pointerEvents: 'none', fontWeight: 600 }}
        >
          {label}
        </text>
      ) : null}
    </g>
  );
};

/**
 * AssetGroupTreemap — Recharts `<Treemap>` wrapper designed for PMax asset
 * groups. Rectangles are sized by `spend` and shaded by `roas` (opacity
 * scale). The lowest ROAS bucket additionally renders a diagonal hatch
 * pattern so the encoding is not color-only (WCAG 1.4.1).
 *
 * A sibling `<table class="sr-only">` exposes the same data to screen
 * readers following the Sprint 1 a11y contract.
 */
const AssetGroupTreemap = ({
  data,
  height = 320,
  currency = 'JMD',
  isLoading = false,
  emptyReasonCode = 'no_pmax_groups',
  ariaLabel,
}: AssetGroupTreemapProps) => {
  // NB architect §10 / S1 §10.10 — avoid `chartPalette[1]` (orange) at low
  // opacity: it fails AA against white. Use the blue series token instead.
  const rootColor = useMemo(() => resolveSeriesColor(0), []);

  const chartData = useMemo(
    () =>
      data.map((d) => ({
        name: d.name,
        value: Math.max(0, Number(d.spend) || 0),
        roas: d.roas ?? 0,
      })),
    [data],
  );

  const tooltipProps = useMemo(
    () => createTooltipProps({ valueType: 'currency', currency }),
    [currency],
  );

  const TreemapComponent = Treemap as unknown as ComponentType<Record<string, unknown>>;
  const TooltipComponent = Tooltip as unknown as ComponentType<Record<string, unknown>>;

  if (isLoading) {
    return <ChartSkeleton variant="bar" height={height} />;
  }

  if (!data || data.length === 0) {
    return (
      <EmptyState
        icon={<VizEmptyIcon />}
        title="No asset groups to display"
        message="There are no Performance Max asset groups for the selected range."
        reasonCode={emptyReasonCode}
      />
    );
  }

  const rootStyle: CSSProperties = { width: '100%' };

  return (
    <div style={rootStyle}>
      {/* Hoisted <defs> so the hatch pattern is always mounted, independent of
          Recharts' treemap cell lifecycle (custom `content` skips inline defs). */}
      <svg aria-hidden="true" width="0" height="0" style={{ position: 'absolute' }}>
        <defs>
          <pattern
            id="viz-treemap-hatch"
            patternUnits="userSpaceOnUse"
            width="8"
            height="8"
            patternTransform="rotate(45)"
          >
            <rect width="8" height="8" fill={rootColor} fillOpacity={0.35} />
            <line
              x1="0"
              y1="0"
              x2="0"
              y2="8"
              stroke="#0f172a"
              strokeWidth={1.5}
              opacity={0.55}
            />
          </pattern>
        </defs>
      </svg>
      <div role="img" aria-label={ariaLabel} style={{ width: '100%' }}>
        <ResponsiveContainer width="100%" height={height}>
          <TreemapComponent
            data={chartData}
            dataKey="value"
            nameKey="name"
            aspectRatio={4 / 3}
            isAnimationActive={false}
            stroke="var(--color-surface-card, #ffffff)"
            fill={rootColor}
            content={(props: unknown) => (
              <TreemapCell
                {...(props as TreemapCellProps)}
                rootColor={rootColor}
              />
            )}
          >
            <TooltipComponent {...tooltipProps} />
          </TreemapComponent>
        </ResponsiveContainer>
      </div>
      <table className="sr-only" aria-label={ariaLabel}>
        <caption>{ariaLabel}</caption>
        <thead>
          <tr>
            <th scope="col">Asset Group</th>
            <th scope="col">Spend</th>
            <th scope="col">ROAS</th>
          </tr>
        </thead>
        <tbody>
          {data.map((row) => (
            <tr key={row.name}>
              <th scope="row">{row.name}</th>
              <td>{formatCurrency(row.spend, currency)}</td>
              <td>
                {row.roas != null && Number.isFinite(row.roas)
                  ? `${formatCompactNumber(row.roas)}x`
                  : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default AssetGroupTreemap;
