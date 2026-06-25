import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import GridCanvas from '../GridCanvas';
import WidgetRenderer from '../WidgetRenderer';
import { slbSampleLayout } from '../sampleLayouts';
import { isDashboardLayoutConfig, type DashboardLayoutConfig } from '../layoutSchema';

describe('GridCanvas', () => {
  it('renders one cell per widget in the config', () => {
    render(<GridCanvas layout={slbSampleLayout} />);
    const cells = document.querySelectorAll('.report-grid__cell');
    expect(cells.length).toBe(slbSampleLayout.widgets.length);
  });

  it('renders KPI labels and chart titles (no duplicate headings)', () => {
    render(<GridCanvas layout={slbSampleLayout} />);
    // KPI self-titles via its label; the cell does NOT repeat it.
    expect(screen.getByText('Followers')).toBeInTheDocument();
    expect(document.querySelector('[data-widget-id="kpi-followers"] .report-grid__title')).toBeNull();
    // A bar chart is title-less, so the cell heading supplies the title.
    const barHeading = document.querySelector('[data-widget-id="bar-top-posts"] .report-grid__title');
    expect(barHeading?.textContent).toBe('Top posts by reactions');
  });

  it('positions a widget from its {x, y, w, h}', () => {
    render(<GridCanvas layout={slbSampleLayout} />);
    const cell = document.querySelector('[data-widget-id="kpi-shares"]') as HTMLElement;
    expect(cell.style.gridColumn).toBe('7 / span 3');
    expect(cell.style.gridRow).toBe('1 / span 2');
  });

  it('binds live data via resolveData (overriding inline data)', () => {
    const layout: DashboardLayoutConfig = {
      id: 'one',
      title: 'One',
      cols: 12,
      rowHeight: 64,
      widgets: [
        { id: 'k', type: 'kpi', title: 'Count', x: 1, y: 1, w: 3, h: 2, data: 1, options: { format: 'number' } },
      ],
    };
    render(<GridCanvas layout={layout} resolveData={() => 999} />);
    expect(screen.getByText(/999/)).toBeInTheDocument();
  });
});

describe('WidgetRenderer', () => {
  it('degrades gracefully for an unknown widget type', () => {
    render(
      <WidgetRenderer
        widget={{ id: 'x', type: 'bogus' as never, x: 1, y: 1, w: 1, h: 1 }}
      />,
    );
    expect(screen.getByText(/unsupported widget type/i)).toBeInTheDocument();
  });
});

describe('isDashboardLayoutConfig', () => {
  it('accepts a valid config and rejects junk', () => {
    expect(isDashboardLayoutConfig(slbSampleLayout)).toBe(true);
    expect(isDashboardLayoutConfig({})).toBe(false);
    expect(isDashboardLayoutConfig({ id: 'x', title: 't', widgets: [{ id: 'a' }] })).toBe(false);
  });
});
