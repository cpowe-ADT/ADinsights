import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from 'react';

import WidgetRenderer from './WidgetRenderer';
import WidgetConfigPanel from './WidgetConfigPanel';
import { clampMove, clampResize, columnPixels, nextFreeRow, pxToUnits } from './gridMath';
import {
  DEFAULT_GRID_COLS,
  DEFAULT_ROW_HEIGHT,
  type DashboardLayoutConfig,
  type DashboardWidget,
  type WidgetOptions,
  type WidgetType,
} from './layoutSchema';
import './reportLayout.css';

/** Matches the grid `gap` (var(--space-4) fallback) used in reportLayout.css. */
const GAP_PX = 16;

const PALETTE: ReadonlyArray<{ type: WidgetType; label: string }> = [
  { type: 'kpi', label: 'KPI' },
  { type: 'bar', label: 'Bar' },
  { type: 'pie', label: 'Pie' },
  { type: 'gauge', label: 'Gauge' },
  { type: 'table', label: 'Table' },
  { type: 'note', label: 'Note' },
];

let counter = 0;
const newId = (): string => `w-${(counter += 1).toString(36)}`;

const placeholderData = (type: WidgetType): unknown => {
  switch (type) {
    case 'kpi':
      return 1234;
    case 'gauge':
      return 0.8;
    case 'bar':
    case 'pie':
      return [
        { label: 'A', value: 3 },
        { label: 'B', value: 2 },
        { label: 'C', value: 1 },
      ];
    case 'table':
      return [{ label: 'Row 1', value: 1 }];
    default:
      return undefined;
  }
};

const placeholderOptions = (type: WidgetType): WidgetOptions => {
  switch (type) {
    case 'kpi':
      return { format: 'number' };
    case 'gauge':
      return { max: 1.2, unit: '%' };
    case 'table':
      return {
        columns: [
          { key: 'label', header: 'Label' },
          { key: 'value', header: 'Value', align: 'right' },
        ],
      };
    case 'note':
      return { text: 'New note' };
    default:
      return { height: 200 };
  }
};

interface DragState {
  id: string;
  mode: 'move' | 'resize';
  startX: number;
  startY: number;
  cellWidth: number;
  cellHeight: number;
  origin: DashboardWidget;
}

export interface LayoutEditorProps {
  layout: DashboardLayoutConfig;
  onChange: (layout: DashboardLayoutConfig) => void;
  onSave?: (layout: DashboardLayoutConfig) => void;
  /** Optional live-data binding so widgets show real values while editing. */
  resolveData?: (widget: DashboardWidget) => unknown;
}

/**
 * Drag-and-drop editor over a {@link DashboardLayoutConfig}. Drag a widget's
 * header to move it, drag the corner to resize, add from the palette, remove via
 * the ×, and save. It only mutates the config — the same config {@link GridCanvas}
 * renders read-only — so the view and editor never drift.
 */
const LayoutEditor = ({ layout, onChange, onSave, resolveData }: LayoutEditorProps) => {
  const cols = layout.cols || DEFAULT_GRID_COLS;
  const rowHeight = layout.rowHeight || DEFAULT_ROW_HEIGHT;
  const containerRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<DragState | null>(null);
  // Freshest props for the once-bound window handlers (no listener churn).
  const latest = useRef({ layout, onChange, cols });
  latest.current = { layout, onChange, cols };
  const [activeId, setActiveId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const updateWidget = useCallback(
    (id: string, patch: Partial<DashboardWidget>) => {
      onChange({
        ...layout,
        widgets: layout.widgets.map((w) => (w.id === id ? { ...w, ...patch } : w)),
      });
    },
    [layout, onChange],
  );

  const applyDrag = useCallback((clientX: number, clientY: number) => {
    const drag = dragRef.current;
    if (!drag) return;
    const { layout: cur, onChange: change, cols: c } = latest.current;
    const dx = pxToUnits(clientX - drag.startX, drag.cellWidth);
    const dy = pxToUnits(clientY - drag.startY, drag.cellHeight);
    const next =
      drag.mode === 'move'
        ? clampMove(drag.origin, dx, dy, c)
        : clampResize(drag.origin, dx, dy, c);
    change({
      ...cur,
      widgets: cur.widgets.map((w) => (w.id === drag.id ? { ...w, ...next } : w)),
    });
  }, []);

  useEffect(() => {
    const move = (e: PointerEvent) => {
      if (dragRef.current) applyDrag(e.clientX, e.clientY);
    };
    const up = () => {
      dragRef.current = null;
      setActiveId(null);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
    return () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
  }, [applyDrag]);

  const beginDrag = useCallback(
    (e: ReactPointerEvent, widget: DashboardWidget, mode: 'move' | 'resize') => {
      e.preventDefault();
      e.stopPropagation();
      const width = containerRef.current?.getBoundingClientRect().width ?? 0;
      dragRef.current = {
        id: widget.id,
        mode,
        startX: e.clientX,
        startY: e.clientY,
        cellWidth: columnPixels(width, cols, GAP_PX),
        cellHeight: rowHeight + GAP_PX,
        origin: widget,
      };
      setActiveId(widget.id);
    },
    [cols, rowHeight],
  );

  const addWidget = useCallback(
    (type: WidgetType) => {
      const widget: DashboardWidget = {
        id: newId(),
        type,
        title: type === 'note' ? 'Note' : type.toUpperCase(),
        x: 1,
        y: nextFreeRow(layout.widgets),
        w: type === 'kpi' ? 3 : 4,
        h: type === 'kpi' ? 2 : 3,
        data: placeholderData(type),
        options: placeholderOptions(type),
      };
      onChange({ ...layout, widgets: [...layout.widgets, widget] });
    },
    [layout, onChange],
  );

  const removeWidget = useCallback(
    (id: string) => {
      setSelectedId((cur) => (cur === id ? null : cur));
      onChange({ ...layout, widgets: layout.widgets.filter((w) => w.id !== id) });
    },
    [layout, onChange],
  );

  const selectedWidget = layout.widgets.find((w) => w.id === selectedId) ?? null;

  return (
    <div className="report-editor">
      <div className="report-editor__toolbar" role="toolbar" aria-label="Layout editor">
        <span className="report-editor__group-label">Add</span>
        {PALETTE.map((item) => (
          <button
            key={item.type}
            type="button"
            className="report-editor__add"
            onClick={() => addWidget(item.type)}
            aria-label={`Add ${item.label} widget`}
          >
            + {item.label}
          </button>
        ))}
        {onSave ? (
          <button
            type="button"
            className="report-editor__save"
            onClick={() => onSave(latest.current.layout)}
          >
            Save layout
          </button>
        ) : null}
      </div>

      {selectedWidget ? (
        <WidgetConfigPanel
          widget={selectedWidget}
          onChange={(patch) => updateWidget(selectedWidget.id, patch)}
          onClose={() => setSelectedId(null)}
        />
      ) : null}

      <section
        ref={containerRef}
        className="report-grid report-grid--editing"
        style={{
          gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
          gridAutoRows: `${rowHeight}px`,
        }}
        aria-label={`${layout.title} (editing)`}
      >
        {layout.widgets.map((widget) => (
          <article
            key={widget.id}
            className={[
              'report-grid__cell',
              'report-grid__cell--editable',
              activeId === widget.id ? 'is-active' : '',
              selectedId === widget.id ? 'is-selected' : '',
            ]
              .filter(Boolean)
              .join(' ')}
            style={{
              gridColumn: `${widget.x} / span ${widget.w}`,
              gridRow: `${widget.y} / span ${widget.h}`,
            }}
            data-widget-id={widget.id}
            data-widget-type={widget.type}
          >
            <header
              className="report-editor__drag"
              onPointerDown={(e) => beginDrag(e, widget, 'move')}
              title="Drag to move"
            >
              <span className="report-editor__drag-grip" aria-hidden="true">
                ⠿
              </span>
              <span className="report-editor__drag-title">{widget.title ?? widget.type}</span>
              <button
                type="button"
                className="report-editor__settings"
                onPointerDown={(e) => e.stopPropagation()}
                onClick={() => setSelectedId(widget.id)}
                aria-label={`Configure ${widget.title ?? widget.type}`}
              >
                ⚙
              </button>
              <button
                type="button"
                className="report-editor__remove"
                onPointerDown={(e) => e.stopPropagation()}
                onClick={() => removeWidget(widget.id)}
                aria-label={`Remove ${widget.title ?? widget.type}`}
              >
                ×
              </button>
            </header>
            <div className="report-grid__body report-editor__body">
              <WidgetRenderer widget={widget} data={resolveData?.(widget)} />
            </div>
            <span
              className="report-editor__resize"
              onPointerDown={(e) => beginDrag(e, widget, 'resize')}
              role="separator"
              aria-label={`Resize ${widget.title ?? widget.type}`}
              title="Drag to resize"
            />
          </article>
        ))}
      </section>
    </div>
  );
};

export default LayoutEditor;
