import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import LayoutEditor from '../LayoutEditor';
import type { DashboardLayoutConfig } from '../layoutSchema';

const baseLayout: DashboardLayoutConfig = {
  id: 'test',
  title: 'Test',
  cols: 12,
  rowHeight: 64,
  widgets: [
    { id: 'a', type: 'kpi', title: 'Alpha', x: 1, y: 1, w: 3, h: 2, data: 1, options: { format: 'number' } },
  ],
};

describe('LayoutEditor', () => {
  it('renders the palette toolbar and a draggable header per widget', () => {
    render(<LayoutEditor layout={baseLayout} onChange={() => {}} />);
    expect(screen.getByRole('toolbar', { name: /layout editor/i })).toBeInTheDocument();
    expect(screen.getByLabelText('Add Bar widget')).toBeInTheDocument();
    // The widget's drag header shows its title.
    expect(document.querySelector('.report-editor__drag-title')?.textContent).toBe('Alpha');
  });

  it('adds a widget from the palette at the next free row', () => {
    const onChange = vi.fn();
    render(<LayoutEditor layout={baseLayout} onChange={onChange} />);
    fireEvent.click(screen.getByLabelText('Add Bar widget'));
    expect(onChange).toHaveBeenCalledTimes(1);
    const next = onChange.mock.calls[0][0] as DashboardLayoutConfig;
    expect(next.widgets).toHaveLength(2);
    const added = next.widgets[1];
    expect(added.type).toBe('bar');
    expect(added.y).toBe(3); // below the 1..2 KPI
  });

  it('removes a widget', () => {
    const onChange = vi.fn();
    render(<LayoutEditor layout={baseLayout} onChange={onChange} />);
    fireEvent.click(screen.getByLabelText('Remove Alpha'));
    const next = onChange.mock.calls[0][0] as DashboardLayoutConfig;
    expect(next.widgets).toHaveLength(0);
  });

  it('saves the current layout', () => {
    const onSave = vi.fn();
    render(<LayoutEditor layout={baseLayout} onChange={() => {}} onSave={onSave} />);
    fireEvent.click(screen.getByText('Save layout'));
    expect(onSave).toHaveBeenCalledWith(baseLayout);
  });

  it('hides the Save button when no onSave is provided', () => {
    render(<LayoutEditor layout={baseLayout} onChange={() => {}} />);
    expect(screen.queryByText('Save layout')).toBeNull();
  });
});
