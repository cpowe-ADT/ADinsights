import {
  useCallback,
  useEffect,
  useMemo,
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
  type WidgetMetricAvailabilityState,
  type WidgetSourceBinding,
  type WidgetOptions,
  type WidgetType,
  widgetSourceSignature,
} from './layoutSchema';
import './reportLayout.css';

/** Matches the grid `gap` (var(--space-4) fallback) used in reportLayout.css. */
const GAP_PX = 16;

const PALETTE: ReadonlyArray<{ type: WidgetType; label: string }> = [
  { type: 'kpi', label: 'KPI' },
  { type: 'bar', label: 'Bar' },
  { type: 'line', label: 'Line' },
  { type: 'pie', label: 'Pie' },
  { type: 'gauge', label: 'Gauge' },
  { type: 'table', label: 'Table' },
  { type: 'note', label: 'Note' },
];
const DEFAULT_PLACEHOLDER_WIDGET_TYPES: readonly WidgetType[] = PALETTE.map((item) => item.type);
const SOURCE_STATE_LABELS = {
  available: 'available',
  callable_no_data: 'no data',
  permission_gated: 'gated',
  unsupported: 'unsupported',
} as const;
const SOURCE_STATE_PRIORITY = {
  unsupported: 4,
  permission_gated: 3,
  callable_no_data: 2,
  available: 1,
} satisfies Record<WidgetMetricAvailabilityState, number>;

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
    case 'line':
      return [
        { date: '2026-05-01', value: 2 },
        { date: '2026-05-02', value: 5 },
        { date: '2026-05-03', value: 3 },
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
    case 'line':
      return { height: 200, series: [{ key: 'value', label: 'Value' }], yFormat: 'number' };
    case 'note':
      return { text: 'New note' };
    default:
      return { height: 200 };
  }
};

function sourceAvailability(source?: WidgetSourceBinding): {
  label: string;
  tone: 'available' | 'warning' | 'blocked';
  disabled: boolean;
} | null {
  const states = source?.availability?.map((entry) => entry.state) ?? [];
  if (states.length === 0) return null;
  let state = states[0];
  for (const candidate of states) {
    if (SOURCE_STATE_PRIORITY[candidate] > SOURCE_STATE_PRIORITY[state]) {
      state = candidate;
    }
  }
  if (state === 'unsupported' || state === 'permission_gated') {
    return { label: SOURCE_STATE_LABELS[state], tone: 'blocked', disabled: true };
  }
  if (state === 'callable_no_data') {
    return { label: SOURCE_STATE_LABELS[state], tone: 'warning', disabled: false };
  }
  return { label: SOURCE_STATE_LABELS[state], tone: 'available', disabled: false };
}

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
  /**
   * Governed source widgets, typically adapted from the backend report preview.
   * When supplied, editors can restore missing source-bound widgets without
   * creating placeholder-only components.
   */
  availableWidgets?: DashboardWidget[];
  /** Placeholder widget types available from the generic palette. */
  placeholderWidgetTypes?: readonly WidgetType[];
}

/**
 * Drag-and-drop editor over a {@link DashboardLayoutConfig}. Drag a widget's
 * header to move it, drag the corner to resize, add from the palette, remove via
 * the ×, and save. It only mutates the config — the same config {@link GridCanvas}
 * renders read-only — so the view and editor never drift.
 */
const LayoutEditor = ({
  layout,
  onChange,
  onSave,
  resolveData,
  availableWidgets = [],
  placeholderWidgetTypes = DEFAULT_PLACEHOLDER_WIDGET_TYPES,
}: LayoutEditorProps) => {
  const cols = layout.cols || DEFAULT_GRID_COLS;
  const rowHeight = layout.rowHeight || DEFAULT_ROW_HEIGHT;
  const containerRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<DragState | null>(null);
  // Freshest props for the once-bound window handlers (no listener churn).
  const latest = useRef({ layout, onChange, cols });
  latest.current = { layout, onChange, cols };
  const [activeId, setActiveId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedSourceWidgetId, setSelectedSourceWidgetId] = useState('');

  const sourceWidgetChoices = useMemo(() => {
    const currentIds = new Set(layout.widgets.map((widget) => widget.id));
    const currentSourceSignatures = new Set(
      layout.widgets.flatMap((widget) => {
        const signature = widgetSourceSignature(widget);
        return signature ? [signature] : [];
      }),
    );
    return availableWidgets.filter((widget) => {
      if (currentIds.has(widget.id)) return false;
      const signature = widgetSourceSignature(widget);
      return !signature || !currentSourceSignatures.has(signature);
    });
  }, [availableWidgets, layout.widgets]);
  const selectedSourceWidget = sourceWidgetChoices.find(
    (widget) => widget.id === selectedSourceWidgetId,
  );
  const selectedSourceAvailability = sourceAvailability(selectedSourceWidget?.source);
  const placeholderPalette = useMemo(() => {
    const allowedTypes = new Set(placeholderWidgetTypes);
    return PALETTE.filter((item) => allowedTypes.has(item.type));
  }, [placeholderWidgetTypes]);

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

  useEffect(() => {
    if (
      selectedSourceWidgetId &&
      !sourceWidgetChoices.some((widget) => widget.id === selectedSourceWidgetId)
    ) {
      setSelectedSourceWidgetId('');
    }
  }, [selectedSourceWidgetId, sourceWidgetChoices]);

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

  const addSourceWidget = useCallback(() => {
    const sourceWidget = sourceWidgetChoices.find((widget) => widget.id === selectedSourceWidgetId);
    if (!sourceWidget) return;
    if (sourceAvailability(sourceWidget.source)?.disabled) return;
    const nextWidget: DashboardWidget = {
      ...sourceWidget,
      x: Math.min(Math.max(sourceWidget.x || 1, 1), cols),
      y: nextFreeRow(layout.widgets),
    };
    onChange({ ...layout, widgets: [...layout.widgets, nextWidget] });
    setSelectedSourceWidgetId('');
    setSelectedId(nextWidget.id);
  }, [cols, layout, onChange, selectedSourceWidgetId, sourceWidgetChoices]);

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
        {placeholderPalette.map((item) => (
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
        {sourceWidgetChoices.length > 0 ? (
          <div className="report-editor__catalog">
            <label className="report-editor__catalog-field">
              <span className="report-editor__group-label">Governed</span>
              <select
                value={selectedSourceWidgetId}
                onChange={(event) => setSelectedSourceWidgetId(event.target.value)}
                aria-label="Governed report widget"
              >
                <option value="">Select widget</option>
                {sourceWidgetChoices.map((widget) => {
                  const availability = sourceAvailability(widget.source);
                  return (
                    <option
                      key={widget.id}
                      value={widget.id}
                      disabled={availability?.disabled ?? false}
                    >
                      {widget.title ?? widget.id}
                      {availability ? ` (${availability.label})` : ''}
                    </option>
                  );
                })}
              </select>
            </label>
            <button
              type="button"
              className="report-editor__add"
              onClick={addSourceWidget}
              disabled={!selectedSourceWidgetId || Boolean(selectedSourceAvailability?.disabled)}
            >
              Add governed widget
            </button>
          </div>
        ) : null}
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
        {layout.widgets.map((widget) => {
          const availability = sourceAvailability(widget.source);
          return (
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
                {availability ? (
                  <span
                    className={`report-editor__availability report-editor__availability--${availability.tone}`}
                  >
                    {availability.label}
                  </span>
                ) : null}
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
          );
        })}
      </section>
    </div>
  );
};

export default LayoutEditor;
