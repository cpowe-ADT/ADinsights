import type { Meta, StoryObj } from '@storybook/react';

import ChartSkeleton from './ChartSkeleton';

const meta: Meta<typeof ChartSkeleton> = {
  title: 'Viz/ChartSkeleton',
  component: ChartSkeleton,
  parameters: {
    layout: 'padded',
    a11y: { config: { rules: [{ id: 'color-contrast', enabled: true }] } },
    chromatic: { viewports: [375, 1280] },
  },
  tags: ['autodocs'],
};
export default meta;

type Story = StoryObj<typeof ChartSkeleton>;

export const Line: Story = { args: { variant: 'line', height: 260 } };
export const Bar: Story = { args: { variant: 'bar', height: 260 } };
export const Pie: Story = { args: { variant: 'pie', height: 260 } };
export const Table: Story = { args: { variant: 'table', rows: 6 } };
export const KpiStrip: Story = { args: { variant: 'kpi-strip' } };
export const Kpi: Story = { args: { variant: 'kpi', height: 96 } };
export const Sparkline: Story = { args: { variant: 'sparkline', height: 40 } };
export const Bubble: Story = { args: { variant: 'bubble', height: 320 } };
