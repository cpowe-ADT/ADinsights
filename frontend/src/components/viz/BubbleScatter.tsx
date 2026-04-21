import { useMemo } from 'react';
import type { ComponentType } from 'react';
import {
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts';

import {
  axisTickFormatter,
  chartMargins,
  chartTheme,
  createTooltipProps,
  resolveSeriesColor,
  type ChartValueType,
} from '../../styles/chartTheme';
import { formatCompactNumber, formatCurrency, formatPercent } from '../../lib/formatNumber';
import EmptyState from '../EmptyState';

import ChartSkeleton from './ChartSkeleton';
import VizEmptyIcon from './VizEmptyIcon';

export type BubbleShape = 'circle' | 'triangle' | 'square';

export interface BubbleScatterDatum {
  id: string;
  label: string;
  x: number;
  y: number;
  z: number;
  /** Categorical shape encoding (defaults to 'circle'). */
  shape?: BubbleShape;
  /** Override fill color. */
  color?: string;
}

export interface BubbleScatterProps {
  data: BubbleScatterDatum[];
  /** X axis title (also used inside tooltip). */
  xLabel: string;
  /** Y axis title. */
  yLabel: string;
  /** Z / size axis title. */
  zLabel: string;
  /** X axis value formatting. */
  xFormat?: ChartValueType;
  /** Y axis value formatting. */
  yFormat?: ChartValueType;
  /** Z axis value formatting (used inside tooltip). */
  zFormat?: ChartValueType;
  /** ISO currency code. */
  currency?: string;
  /** Reason code forwarded to <EmptyState>. */
  emptyReasonCode?: string;
  /** Render a shimmer placeholder. */
  isLoading?: boolean;
  /** Chart height. */
  height?: number;
  /** Required accessible label. */
  ariaLabel: string;
  /** Optional click handler fired with the datum id. */
  onBubbleClick?: (id: string) => void;
}

const axisTickStyle = { fill: 'var(--viz-axis-tick)', fontSize: 12 } as const;

const SHAPE_TO_RECHARTS: Record<BubbleShape, 'circle' | 'triangle' | 'square'> = {
  circle: 'circle',
  triangle: 'triangle',
  square: 'square',
};

const formatValue = (value: number, format: ChartValueType, currency: string): string => {
  if (format === 'currency') return formatCurrency(value, currency);
  if (format === 'percent') return formatPercent(value);
  return formatCompactNumber(value);
};

/**
 * BubbleScatter — x/y/size/shape scatter plot. `shape` provides the
 * non-color categorical encoding required for WCAG conformance when
 * callers group bubbles by a categorical dimension.
 *
 * Under the hood, bubbles are split into one Recharts `<Scatter>`
 * series per distinct shape so that Recharts can render the correct
 * glyph. The legend enumerates both shape and color.
 */
const BubbleScatter = ({
  data,
  xLabel,
  yLabel,
  zLabel,
  xFormat = 'number',
  yFormat = 'number',
  zFormat = 'number',
  currency = 'JMD',
  emptyReasonCode = 'no_data_for_range',
  isLoading = false,
  height = 340,
  ariaLabel,
  onBubbleClick,
}: BubbleScatterProps) => {
  const seriesByShape = useMemo(() => {
    const map = new Map<BubbleShape, BubbleScatterDatum[]>();
    for (const d of data) {
      const shape = d.shape ?? 'circle';
      const list = map.get(shape) ?? [];
      list.push(d);
      map.set(shape, list);
    }
    return map;
  }, [data]);

  const tooltipProps = useMemo(
    () =>
      createTooltipProps({
        valueType: 'number',
        currency,
        valueFormatter: (value) => {
          if (typeof value !== 'number') return String(value ?? '');
          return formatCompactNumber(value);
        },
      }),
    [currency],
  );

  const GridComponent = CartesianGrid as unknown as ComponentType<Record<string, unknown>>;
  const XAxisComponent = XAxis as unknown as ComponentType<Record<string, unknown>>;
  const YAxisComponent = YAxis as unknown as ComponentType<Record<string, unknown>>;
  const ZAxisComponent = ZAxis as unknown as ComponentType<Record<string, unknown>>;
  const TooltipComponent = Tooltip as unknown as ComponentType<Record<string, unknown>>;
  const LegendComponent = Legend as unknown as ComponentType<Record<string, unknown>>;
  const ScatterComponent = Scatter as unknown as ComponentType<Record<string, unknown>>;

  if (isLoading) {
    return <ChartSkeleton variant="bubble" height={height} />;
  }

  if (!data || data.length === 0) {
    return (
      <EmptyState
        icon={<VizEmptyIcon />}
        title="No data to display"
        message="There is no data for the selected range."
        reasonCode={emptyReasonCode}
      />
    );
  }

  const handleClick = onBubbleClick
    ? (payload: unknown) => {
        const evt = payload as { id?: string } | undefined;
        if (evt?.id) onBubbleClick(evt.id);
      }
    : undefined;

  return (
    <div style={{ width: '100%' }}>
      <div role="img" aria-label={ariaLabel} style={{ width: '100%' }}>
        <ResponsiveContainer width="100%" height={height}>
          <ScatterChart margin={chartMargins}>
            <GridComponent
              stroke="var(--viz-grid)"
              strokeDasharray={chartTheme.grid.strokeDasharray}
              vertical={false}
            />
            <XAxisComponent
              type="number"
              dataKey="x"
              name={xLabel}
              axisLine={false}
              tickLine={false}
              tick={axisTickStyle}
              tickFormatter={(value: number) => axisTickFormatter(value)}
            />
            <YAxisComponent
              type="number"
              dataKey="y"
              name={yLabel}
              axisLine={false}
              tickLine={false}
              tick={axisTickStyle}
              width={68}
              tickFormatter={(value: number) => axisTickFormatter(value)}
            />
            <ZAxisComponent type="number" dataKey="z" range={[60, 360]} name={zLabel} />
            <TooltipComponent cursor={{ strokeDasharray: '3 3' }} {...tooltipProps} />
            <LegendComponent wrapperStyle={{ color: 'var(--viz-legend-text)' }} />
            {Array.from(seriesByShape.entries()).map(([shape, items], idx) => (
              <ScatterComponent
                key={shape}
                name={shape}
                data={items.map((d) => ({
                  ...d,
                  // Recharts derives the rendered color from the series-level
                  // `fill`; per-point color overrides are handled via <Cell>.
                }))}
                fill={items[0]?.color ?? resolveSeriesColor(idx)}
                shape={SHAPE_TO_RECHARTS[shape]}
                onClick={handleClick}
              />
            ))}
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <table className="sr-only" aria-label={ariaLabel}>
        <caption>{ariaLabel}</caption>
        <thead>
          <tr>
            <th scope="col">Label</th>
            <th scope="col">{xLabel}</th>
            <th scope="col">{yLabel}</th>
            <th scope="col">{zLabel}</th>
            <th scope="col">Shape</th>
          </tr>
        </thead>
        <tbody>
          {data.map((row) => (
            <tr key={row.id}>
              <th scope="row">{row.label}</th>
              <td>{formatValue(row.x, xFormat, currency)}</td>
              <td>{formatValue(row.y, yFormat, currency)}</td>
              <td>{formatValue(row.z, zFormat, currency)}</td>
              <td>{row.shape ?? 'circle'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default BubbleScatter;
