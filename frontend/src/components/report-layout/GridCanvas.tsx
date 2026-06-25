import type { CSSProperties, ReactElement } from 'react';

import WidgetRenderer from './WidgetRenderer';
import {
  DEFAULT_GRID_COLS,
  DEFAULT_ROW_HEIGHT,
  type DashboardLayoutConfig,
  type DashboardWidget,
  type WidgetType,
} from './layoutSchema';
import './reportLayout.css';

/** These widgets render their own title (KPI label, gauge label, table heading),
 *  so the cell must not repeat it. */
const SELF_TITLING: ReadonlySet<WidgetType> = new Set(['kpi', 'gauge', 'table']);

export interface GridCanvasProps {
  layout: DashboardLayoutConfig;
  /**
   * Optional live-data binding. When provided, each widget is rendered with the
   * value this returns (falling back to the widget's inline `data`). This is how
   * a saved layout binds to real store data without changing the schema.
   */
  resolveData?: (widget: DashboardWidget) => unknown;
  className?: string;
}

const cellStyle = (w: DashboardWidget): CSSProperties => ({
  gridColumn: `${w.x} / span ${w.w}`,
  gridRow: `${w.y} / span ${w.h}`,
});

/**
 * Read-only renderer for a {@link DashboardLayoutConfig}: a responsive CSS grid
 * that positions each widget by its `{x, y, w, h}`. This is the canvas a
 * drag-and-drop editor will later make interactive — the rendering stays the
 * same; the editor only mutates the config.
 */
const GridCanvas = ({ layout, resolveData, className }: GridCanvasProps): ReactElement => {
  const cols = layout.cols || DEFAULT_GRID_COLS;
  const rowHeight = layout.rowHeight || DEFAULT_ROW_HEIGHT;

  return (
    <section
      className={['report-grid', className].filter(Boolean).join(' ')}
      aria-label={layout.title}
      style={{
        gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
        gridAutoRows: `${rowHeight}px`,
      }}
    >
      {layout.widgets.map((widget) => (
        <article
          key={widget.id}
          className="report-grid__cell"
          style={cellStyle(widget)}
          data-widget-id={widget.id}
          data-widget-type={widget.type}
        >
          {widget.title && !SELF_TITLING.has(widget.type) ? (
            <h3 className="report-grid__title">{widget.title}</h3>
          ) : null}
          <div className="report-grid__body">
            <WidgetRenderer widget={widget} data={resolveData?.(widget)} />
          </div>
        </article>
      ))}
    </section>
  );
};

export default GridCanvas;
