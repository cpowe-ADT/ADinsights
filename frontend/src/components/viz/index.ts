/**
 * Sprint 1 shared viz kit — barrel export.
 *
 * Downstream sprints (Meta, Google, Combined dashboards) should import from
 * here rather than deep-linking into individual files:
 *
 *     import { KpiTile, TrendLine, VizDataTable, EmptyState } from '@/components/viz';
 *
 * The existing `components/EmptyState.tsx` is re-exported as-is; it already
 * satisfies the FP-CC-01 `reasonCode` contract.
 */

// -----------------------------------------------------------------------------
// S1b-owned primitives (this agent)
// -----------------------------------------------------------------------------
export { default as KpiTile } from './KpiTile';
export type { KpiTileProps, KpiFormat } from './KpiTile';

export { default as VizDataTable } from './DataTable';
export type { VizDataTableProps } from './DataTable';

export { default as AccessibleTableToggle } from './AccessibleTableToggle';
export type {
  AccessibleTableToggleProps,
  AccessibleTableToggleView,
} from './AccessibleTableToggle';

// Re-export the existing EmptyState from its canonical location. The viz-kit
// spec intentionally does not fork a copy — Sprint 1 callers use the same
// `reasonCode`-aware component already in `components/EmptyState.tsx`.
export { default as EmptyState } from '../EmptyState';

// -----------------------------------------------------------------------------
// S1a-owned chart primitives
// -----------------------------------------------------------------------------
export { default as TrendLine } from './TrendLine';
export { default as Sparkline } from './Sparkline';
export { default as PeerAvgLine } from './PeerAvgLine';
export { default as ChartSkeleton } from './ChartSkeleton';
export { default as DistributionBar } from './DistributionBar';
export { default as BubbleScatter } from './BubbleScatter';
export { default as PieComposition } from './PieComposition';

// -----------------------------------------------------------------------------
// S3b-CreativeConv-owned primitives (Sprint 3 kit extension)
// -----------------------------------------------------------------------------
export { default as AssetGroupTreemap, roasToOpacity } from './AssetGroupTreemap';
export type {
  AssetGroupTreemapProps,
  AssetGroupTreemapDatum,
} from './AssetGroupTreemap';

export { default as GaugeRing, derivePacingVariant } from './GaugeRing';
export type { GaugeRingProps, GaugeVariant } from './GaugeRing';
