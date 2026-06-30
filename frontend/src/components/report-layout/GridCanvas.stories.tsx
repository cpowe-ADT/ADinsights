import type { Meta, StoryObj } from '@storybook/react';

import GridCanvas from './GridCanvas';
import { slbSampleLayout } from './sampleLayouts';
import type { DashboardLayoutConfig, DashboardWidget } from './layoutSchema';

const meta: Meta<typeof GridCanvas> = {
  title: 'Report Layout/GridCanvas',
  component: GridCanvas,
  parameters: { layout: 'fullscreen' },
};

export default meta;

type Story = StoryObj<typeof GridCanvas>;

export const SlbMonthly: Story = {
  args: { layout: slbSampleLayout },
};

const compactLayout: DashboardLayoutConfig = {
  id: 'compact-demo',
  title: 'Compact demo',
  cols: 6,
  rowHeight: 72,
  widgets: [
    {
      id: 'a',
      type: 'kpi',
      title: 'Spend',
      x: 1,
      y: 1,
      w: 3,
      h: 2,
      data: 478000,
      options: { format: 'currency', currency: 'JMD' },
    },
    {
      id: 'b',
      type: 'gauge',
      title: 'Pacing',
      x: 4,
      y: 1,
      w: 3,
      h: 2,
      data: 0.82,
      options: { max: 1.2, unit: '%' },
    },
    {
      id: 'c',
      type: 'bar',
      title: 'By parish',
      x: 1,
      y: 3,
      w: 6,
      h: 3,
      data: [
        { label: 'Kingston', value: 478000 },
        { label: 'St James', value: 415000 },
        { label: 'St Andrew', value: 352000 },
      ],
      options: { height: 200 },
    },
  ],
};

export const Compact: Story = {
  args: { layout: compactLayout },
};

export const WithLiveDataResolver: Story = {
  args: {
    layout: slbSampleLayout,
    // Demonstrates binding the same config to live values without editing it.
    resolveData: (widget: DashboardWidget) => (widget.id === 'kpi-followers' ? 6100 : undefined),
  },
};
