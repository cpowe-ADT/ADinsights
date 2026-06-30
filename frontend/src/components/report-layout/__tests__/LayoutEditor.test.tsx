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
    {
      id: 'a',
      type: 'kpi',
      title: 'Alpha',
      x: 1,
      y: 1,
      w: 3,
      h: 2,
      data: 1,
      options: { format: 'number' },
    },
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

  it('selects a widget and edits it via the config panel', () => {
    const onChange = vi.fn();
    render(<LayoutEditor layout={baseLayout} onChange={onChange} />);
    // No panel until a widget is selected.
    expect(screen.queryByText('Widget settings')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Configure Alpha' }));
    expect(screen.getByText('Widget settings')).toBeInTheDocument();
    fireEvent.change(screen.getByDisplayValue('Alpha'), { target: { value: 'Renamed' } });
    const next = onChange.mock.calls.at(-1)?.[0] as DashboardLayoutConfig;
    expect(next.widgets[0].title).toBe('Renamed');
  });

  it('restores available governed widgets and blocks gated governed widgets', () => {
    const onChange = vi.fn();
    render(
      <LayoutEditor
        layout={baseLayout}
        onChange={onChange}
        placeholderWidgetTypes={['note']}
        availableWidgets={[
          {
            id: 'page-follows',
            type: 'kpi',
            title: 'Page follows',
            x: 1,
            y: 1,
            w: 3,
            h: 2,
            data: 6023,
            source: {
              dataset: 'organic_facebook_page',
              widgetId: 'organic_summary',
              metrics: ['page_follows'],
              availability: [
                {
                  key: 'page_follows',
                  state: 'available',
                  note: 'Stored rows exist.',
                  rowCount: 31,
                },
              ],
            },
          },
          {
            id: 'page-reach',
            type: 'kpi',
            title: 'Page reach',
            x: 1,
            y: 3,
            w: 3,
            h: 2,
            data: null,
            source: {
              dataset: 'organic_facebook_page',
              widgetId: 'organic_summary',
              metrics: ['page_reach'],
              availability: [
                {
                  key: 'page_reach',
                  state: 'permission_gated',
                  note: 'Requires Meta read_insights approval.',
                  rowCount: 0,
                },
              ],
            },
          },
        ]}
      />,
    );

    expect(screen.queryByLabelText('Add KPI widget')).not.toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Page follows (available)' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Page reach (gated)' })).toBeDisabled();

    fireEvent.change(screen.getByLabelText('Governed report widget'), {
      target: { value: 'page-reach' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Add governed widget' }));
    expect(onChange).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText('Governed report widget'), {
      target: { value: 'page-follows' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Add governed widget' }));

    const next = onChange.mock.calls[0][0] as DashboardLayoutConfig;
    expect(next.widgets.at(-1)).toMatchObject({
      id: 'page-follows',
      title: 'Page follows',
      source: expect.objectContaining({
        availability: [expect.objectContaining({ key: 'page_follows', state: 'available' })],
      }),
    });
  });

  it('does not offer governed widgets already present under a custom id', () => {
    render(
      <LayoutEditor
        layout={{
          ...baseLayout,
          widgets: [
            {
              ...baseLayout.widgets[0],
              id: 'custom-followers',
              source: {
                dataset: 'organic_facebook_page',
                widgetId: 'saved_custom',
                metrics: ['page_follows'],
              },
            },
          ],
        }}
        onChange={() => {}}
        availableWidgets={[
          {
            id: 'catalog-page-follows',
            type: 'kpi',
            title: 'Page follows',
            x: 1,
            y: 1,
            w: 3,
            h: 2,
            data: null,
            source: {
              dataset: 'organic_facebook_page',
              widgetId: 'catalog:organic_facebook_page:page_follows',
              metrics: ['page_follows'],
              availability: [{ key: 'page_follows', state: 'available' }],
            },
          },
        ]}
      />,
    );

    expect(screen.queryByLabelText('Governed report widget')).not.toBeInTheDocument();
  });
});
