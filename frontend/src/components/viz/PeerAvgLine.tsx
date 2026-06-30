import type { ComponentType } from 'react';
import { Line } from 'recharts';

export interface PeerAvgLinePoint {
  date: string;
  value: number;
}

export interface PeerAvgLineProps {
  /** Peer-average series data; typically a median computed by the caller. */
  data: PeerAvgLinePoint[];
  /** Left or right Y axis binding when hosted inside a dual-axis chart. */
  yAxisId?: 'left' | 'right';
  /** Override the default "Peer avg" legend label. */
  name?: string;
}

/**
 * PeerAvgLine — a dashed, faded secondary series used inside `<TrendLine>`
 * to convey "how does this account compare against peer accounts?".
 *
 * Not meant to be rendered standalone. When a `<TrendLine>` receives a
 * `peerData` prop it injects this component as the last Recharts
 * series so that tooltips list it after the primary lines.
 *
 * The actual data is passed through a hidden `<Line>` that reads its
 * series from the parent chart's `data` prop — Recharts requires every
 * `<Line>` to live inside the same chart root. The host `<TrendLine>`
 * merges `peerData` into the chart data before render.
 */
const PeerAvgLine = (props: PeerAvgLineProps) => {
  const { yAxisId, name = 'Peer avg' } = props;
  const LineComponent = Line as unknown as ComponentType<Record<string, unknown>>;

  return (
    <LineComponent
      type="monotone"
      dataKey="__peerAvg"
      name={name}
      stroke="var(--viz-platform-peer-avg)"
      strokeDasharray="4 4"
      strokeWidth={1.5}
      dot={false}
      activeDot={false}
      isAnimationActive={false}
      legendType="plainline"
      yAxisId={yAxisId}
    />
  );
};

export default PeerAvgLine;
