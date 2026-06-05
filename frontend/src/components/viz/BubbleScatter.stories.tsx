import type { Meta, StoryObj } from '@storybook/react';

import BubbleScatter from './BubbleScatter';
import type { BubbleScatterDatum } from './BubbleScatter';

const meta: Meta<typeof BubbleScatter> = {
  title: 'Viz/BubbleScatter',
  component: BubbleScatter,
  parameters: {
    layout: 'padded',
    a11y: { config: { rules: [{ id: 'color-contrast', enabled: true }] } },
    chromatic: { viewports: [375, 1280] },
  },
  tags: ['autodocs'],
};
export default meta;

type Story = StoryObj<typeof BubbleScatter>;

const baseData: BubbleScatterDatum[] = [
  { id: 'c1', label: 'Awareness', x: 12000, y: 0.018, z: 240 },
  { id: 'c2', label: 'Conversion', x: 8400, y: 0.042, z: 180 },
  { id: 'c3', label: 'Remarketing', x: 5200, y: 0.065, z: 140 },
  { id: 'c4', label: 'Search', x: 3400, y: 0.09, z: 90 },
];

const shapedData: BubbleScatterDatum[] = [
  { id: 'm1', label: 'Meta Awareness', x: 12000, y: 0.018, z: 240, shape: 'circle' },
  { id: 'g1', label: 'Google Search', x: 3400, y: 0.09, z: 90, shape: 'triangle' },
  { id: 'm2', label: 'Meta Convert', x: 8400, y: 0.042, z: 180, shape: 'circle' },
  { id: 'g2', label: 'Google Shopping', x: 5200, y: 0.065, z: 140, shape: 'triangle' },
];

const clusteredData: BubbleScatterDatum[] = Array.from({ length: 18 }).map((_, i) => ({
  id: `c-${i}`,
  label: `Campaign ${i + 1}`,
  x: 1000 + ((i * 713) % 9000),
  y: 0.01 + ((i * 17) % 80) / 1000,
  z: 50 + ((i * 37) % 220),
}));

export const Default: Story = {
  args: {
    data: baseData,
    xLabel: 'Spend',
    yLabel: 'CTR',
    zLabel: 'Conversions',
    xFormat: 'currency',
    yFormat: 'percent',
    ariaLabel: 'Campaign CTR vs. spend (bubble size = conversions)',
  },
};

export const Loading: Story = {
  args: {
    data: [],
    isLoading: true,
    xLabel: 'Spend',
    yLabel: 'CTR',
    zLabel: 'Conversions',
    ariaLabel: 'Campaign CTR vs. spend',
  },
};

export const Empty: Story = {
  args: {
    data: [],
    xLabel: 'Spend',
    yLabel: 'CTR',
    zLabel: 'Conversions',
    emptyReasonCode: 'no_data_for_range',
    ariaLabel: 'Campaign CTR vs. spend',
  },
};

export const Clustered: Story = {
  args: {
    data: clusteredData,
    xLabel: 'Spend',
    yLabel: 'CTR',
    zLabel: 'Conversions',
    xFormat: 'currency',
    yFormat: 'percent',
    ariaLabel: 'Campaign cluster scatter',
  },
};

export const WithShapes: Story = {
  args: {
    data: shapedData,
    xLabel: 'Spend',
    yLabel: 'CTR',
    zLabel: 'Conversions',
    xFormat: 'currency',
    yFormat: 'percent',
    ariaLabel: 'Campaign CTR vs. spend by platform',
  },
};

export const DarkTheme: Story = {
  args: {
    data: baseData,
    xLabel: 'Spend',
    yLabel: 'CTR',
    zLabel: 'Conversions',
    xFormat: 'currency',
    yFormat: 'percent',
    ariaLabel: 'Campaign CTR vs. spend',
  },
  decorators: [
    (StoryComponent) => (
      <div data-theme="dark" style={{ background: 'var(--color-surface-card)', padding: 16 }}>
        <StoryComponent />
      </div>
    ),
  ],
};
