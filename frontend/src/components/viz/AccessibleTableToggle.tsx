import { useCallback, useId, useState, type KeyboardEvent, type ReactNode } from 'react';

export type AccessibleTableToggleView = 'chart' | 'table';

export type AccessibleTableToggleProps = {
  chart: ReactNode;
  table: ReactNode;
  /** Initial view — defaults to the chart. */
  defaultView?: AccessibleTableToggleView;
  /**
   * Label describing what the chart represents, used for the chart-view
   * container (`role="group"` / `aria-label`). Keep this caller-provided so
   * every wrapper tells the screen-reader user what the visualization shows.
   */
  chartAriaLabel?: string;
  /**
   * Extra class on the outer wrapper for layout integration.
   */
  className?: string;
};

/**
 * Wraps a chart + an accessible tabular equivalent and exposes a
 * keyboard-reachable toggle between the two views.
 *
 * Structural contract (see `artifacts/sprint/S1-architect-design.md` §5):
 *   - Both children remain mounted at all times. The inactive child gets the
 *     `hidden` attribute + `aria-hidden="true"` so Recharts animation state
 *     is preserved and screen readers do not re-announce on every toggle.
 *   - Toggle button is icon-only, has `aria-pressed`, and has an `aria-label`
 *     that swaps between "Show data table" and "Show chart".
 *   - Space and Enter both activate the toggle (default `<button>` behaviour,
 *     plus explicit key handler as a belt-and-braces backstop for assistive
 *     tech that synthesizes keyup-only events).
 */
const AccessibleTableToggle = ({
  chart,
  table,
  defaultView = 'chart',
  chartAriaLabel,
  className,
}: AccessibleTableToggleProps) => {
  const [view, setView] = useState<AccessibleTableToggleView>(defaultView);
  const chartId = useId();
  const tableId = useId();

  const showingChart = view === 'chart';

  const toggle = useCallback(() => {
    setView((prev) => (prev === 'chart' ? 'table' : 'chart'));
  }, []);

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLButtonElement>) => {
      if (event.key === 'Enter' || event.key === ' ' || event.key === 'Spacebar') {
        event.preventDefault();
        toggle();
      }
    },
    [toggle],
  );

  const mergedClassName = ['viz-table-toggle', className].filter(Boolean).join(' ');

  const buttonLabel = showingChart ? 'Show data table' : 'Show chart';
  const buttonIcon = showingChart ? '⊞' : '📈';

  return (
    <div className={mergedClassName}>
      <div className="viz-table-toggle__controls">
        <button
          type="button"
          className="viz-table-toggle__button"
          onClick={toggle}
          onKeyDown={handleKeyDown}
          aria-pressed={!showingChart}
          aria-label={buttonLabel}
          aria-controls={`${chartId} ${tableId}`}
        >
          <span aria-hidden="true">{buttonIcon}</span>
        </button>
      </div>
      <div
        id={chartId}
        className="viz-table-toggle__chart"
        role="group"
        aria-label={chartAriaLabel}
        hidden={!showingChart}
        aria-hidden={!showingChart}
      >
        {chart}
      </div>
      <div
        id={tableId}
        className="viz-table-toggle__table"
        hidden={showingChart}
        aria-hidden={showingChart}
      >
        {table}
      </div>
    </div>
  );
};

export default AccessibleTableToggle;
