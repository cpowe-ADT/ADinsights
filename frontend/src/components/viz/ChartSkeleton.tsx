import type { CSSProperties } from 'react';

import Skeleton from '../Skeleton';

export type ChartSkeletonVariant =
  | 'line'
  | 'bar'
  | 'pie'
  | 'table'
  | 'kpi-strip'
  | 'kpi'
  | 'sparkline'
  | 'bubble';

export interface ChartSkeletonProps {
  /** Pixel height to match the target chart footprint (prevents CLS). */
  height?: number;
  /** Number of rows (used by the `table` variant). */
  rows?: number;
  /** Variant chooses an internal shape. */
  variant?: ChartSkeletonVariant;
  /** Optional className forwarded to the root element. */
  className?: string;
}

const rootStyle: CSSProperties = {
  width: '100%',
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
};

/**
 * ChartSkeleton — composes the low-level `<Skeleton>` shimmer primitive
 * into a chart-shaped placeholder so that a chart's container reserves
 * identical vertical space before data arrives.
 *
 * Used by every viz primitive via its `isLoading` branch. Renders an
 * `aria-hidden` presentation region so the loading state is not
 * announced twice (screen readers already get "loading" from the
 * parent dashboard).
 */
const ChartSkeleton = ({
  height = 260,
  rows = 6,
  variant = 'line',
  className,
}: ChartSkeletonProps) => {
  const classes = ['viz-chart-skeleton', className].filter(Boolean).join(' ');

  if (variant === 'kpi' || variant === 'sparkline') {
    return (
      <div
        className={classes}
        style={{ ...rootStyle, height, justifyContent: 'center' }}
        role="presentation"
        aria-hidden="true"
      >
        <Skeleton height={variant === 'kpi' ? 28 : height} width="60%" />
        {variant === 'kpi' ? <Skeleton height={14} width="40%" /> : null}
      </div>
    );
  }

  if (variant === 'kpi-strip') {
    return (
      <div
        className={classes}
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: 12,
        }}
        role="presentation"
        aria-hidden="true"
      >
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <Skeleton height={14} width="55%" />
            <Skeleton height={28} width="75%" />
            <Skeleton height={12} width="40%" />
          </div>
        ))}
      </div>
    );
  }

  if (variant === 'table') {
    return (
      <div className={classes} style={rootStyle} role="presentation" aria-hidden="true">
        <Skeleton height={32} />
        {Array.from({ length: Math.max(1, rows) }).map((_, i) => (
          <Skeleton key={i} height={20} />
        ))}
      </div>
    );
  }

  if (variant === 'pie') {
    return (
      <div
        className={classes}
        style={{
          ...rootStyle,
          height,
          alignItems: 'center',
          justifyContent: 'center',
        }}
        role="presentation"
        aria-hidden="true"
      >
        <Skeleton
          width={Math.min(height - 32, 200)}
          height={Math.min(height - 32, 200)}
          borderRadius="50%"
        />
      </div>
    );
  }

  if (variant === 'bubble') {
    // Scattered circles of varying size across the footprint.
    const bubbles: Array<{ top: string; left: string; size: number }> = [
      { top: '22%', left: '18%', size: 38 },
      { top: '55%', left: '40%', size: 56 },
      { top: '30%', left: '68%', size: 44 },
      { top: '70%', left: '82%', size: 30 },
    ];
    return (
      <div
        className={classes}
        style={{ ...rootStyle, height, position: 'relative' }}
        role="presentation"
        aria-hidden="true"
      >
        {bubbles.map((b, i) => (
          <div
            key={i}
            style={{
              position: 'absolute',
              top: b.top,
              left: b.left,
            }}
          >
            <Skeleton width={b.size} height={b.size} borderRadius="50%" />
          </div>
        ))}
      </div>
    );
  }

  if (variant === 'bar') {
    const barCount = 7;
    const innerHeight = Math.max(24, height - 48);
    return (
      <div
        className={classes}
        style={{ ...rootStyle, height }}
        role="presentation"
        aria-hidden="true"
      >
        <div
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'flex-end',
            gap: 10,
            paddingInline: 12,
          }}
        >
          {Array.from({ length: barCount }).map((_, i) => {
            const factor = 0.35 + ((i * 13) % 60) / 100;
            return (
              <Skeleton
                key={i}
                height={Math.round(innerHeight * factor)}
                width={`${100 / barCount - 2}%`}
                borderRadius={6}
              />
            );
          })}
        </div>
        <Skeleton height={12} width="80%" />
      </div>
    );
  }

  // Default: line variant — tall shimmer block plus two axis-tick lines.
  const lineHeight = Math.max(48, height - 64);
  return (
    <div
      className={classes}
      style={{ ...rootStyle, height }}
      role="presentation"
      aria-hidden="true"
    >
      <Skeleton height={lineHeight} borderRadius={10} />
      <div style={{ display: 'flex', gap: 12 }}>
        <Skeleton height={12} width="40%" />
        <Skeleton height={12} width="25%" />
      </div>
    </div>
  );
};

export default ChartSkeleton;
