/**
 * Pure grid math for the drag-and-drop editor. Kept free of React/DOM so the
 * tricky bits (pixel→grid conversion, bounds clamping) are unit-testable without
 * a layout engine.
 */
import type { DashboardWidget } from './layoutSchema';

/** Effective pixels per grid column, given container width, column count, and gap. */
export function columnPixels(containerWidth: number, cols: number, gapPx: number): number {
  if (cols <= 0 || !Number.isFinite(containerWidth) || containerWidth <= 0) return 0;
  // Treat each column as its share of the content plus one gap — good enough for
  // snap-to-grid, and avoids off-by-one drift as widgets span multiple columns.
  return (containerWidth + gapPx) / cols;
}

/** Convert a pixel delta to a signed, snapped grid-unit delta. */
export function pxToUnits(deltaPx: number, cellSizePx: number): number {
  if (!Number.isFinite(cellSizePx) || cellSizePx <= 0) return 0;
  return Math.round(deltaPx / cellSizePx);
}

/** New {x, y} for a moved widget, clamped inside the grid (1-based). */
export function clampMove(
  widget: DashboardWidget,
  dxUnits: number,
  dyUnits: number,
  cols: number,
): { x: number; y: number } {
  const maxX = Math.max(cols - widget.w + 1, 1);
  const x = Math.min(Math.max(widget.x + dxUnits, 1), maxX);
  const y = Math.max(widget.y + dyUnits, 1);
  return { x, y };
}

/** New {w, h} for a resized widget, clamped to >=1 and within the column count. */
export function clampResize(
  widget: DashboardWidget,
  dwUnits: number,
  dhUnits: number,
  cols: number,
): { w: number; h: number } {
  const maxW = Math.max(cols - widget.x + 1, 1);
  const w = Math.min(Math.max(widget.w + dwUnits, 1), maxW);
  const h = Math.max(widget.h + dhUnits, 1);
  return { w, h };
}

/** Lowest free row (1-based) below all current widgets — where a new widget lands. */
export function nextFreeRow(widgets: DashboardWidget[]): number {
  return widgets.reduce((max, w) => Math.max(max, w.y + w.h), 1);
}
