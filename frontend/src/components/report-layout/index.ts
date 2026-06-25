/**
 * Config-driven report layout — the foundation for customizable views and a
 * future drag-and-drop editor. A layout is data ({@link DashboardLayoutConfig});
 * {@link GridCanvas} renders it from the shared viz kit.
 */
export { default as GridCanvas } from './GridCanvas';
export type { GridCanvasProps } from './GridCanvas';
export { default as WidgetRenderer } from './WidgetRenderer';
export type { WidgetRendererProps } from './WidgetRenderer';
export { slbSampleLayout } from './sampleLayouts';
export {
  DEFAULT_GRID_COLS,
  DEFAULT_ROW_HEIGHT,
  isDashboardLayoutConfig,
} from './layoutSchema';
export type {
  DashboardLayoutConfig,
  DashboardWidget,
  WidgetOptions,
  WidgetPlacement,
  WidgetType,
  TableColumn,
} from './layoutSchema';
