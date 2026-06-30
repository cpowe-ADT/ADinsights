import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { DashboardWidgetPreviewResponse } from '../../../lib/phase2Api';
import GovernedWidgetRenderer from '../GovernedWidgetRenderer';

const baseWidget = {
  widget_id: 'organic_widget',
  dataset: 'organic_facebook_posts',
  status: 'rendered',
  coverage: null,
  warnings: [],
  data: {},
} satisfies Partial<DashboardWidgetPreviewResponse>;

describe('GovernedWidgetRenderer', () => {
  it('preserves missing line values as no data instead of zero', () => {
    render(
      <GovernedWidgetRenderer
        widget={{
          ...baseWidget,
          widget_id: 'organic_trend',
          type: 'line_chart',
          data: {
            title: 'Organic engagement trend',
            x: 'date',
            rows: [
              { date: '2026-05-01', post_reactions: 2, post_shares: null },
              { date: '2026-05-02', post_reactions: 3, post_shares: 1 },
            ],
          },
        }}
      />,
    );

    const table = screen.getByRole('table', { name: 'Organic engagement trend trend' });
    expect(within(table).getByRole('row', { name: /2026-05-01 2 \u2014/ })).toBeInTheDocument();
    expect(within(table).queryByRole('row', { name: /2026-05-01 2 0/ })).not.toBeInTheDocument();
  });

  it('omits missing bar rows instead of rendering a zero bar', () => {
    render(
      <GovernedWidgetRenderer
        widget={{
          ...baseWidget,
          widget_id: 'top_posts',
          type: 'bar_chart',
          data: {
            title: 'Top posts by shares',
            x: 'post',
            rows: [
              { post: 'Measured post', post_shares: 8 },
              { post: 'Unavailable post', post_shares: null },
            ],
          },
        }}
      />,
    );

    const table = screen.getByRole('table', { name: 'Top posts by shares bar chart' });
    expect(within(table).getByRole('row', { name: /Measured post 8/ })).toBeInTheDocument();
    expect(within(table).queryByText('Unavailable post')).not.toBeInTheDocument();
  });
});
