import type { Meta, StoryObj } from '@storybook/react';

import AssetGroupTreemap from './AssetGroupTreemap';

const meta: Meta<typeof AssetGroupTreemap> = {
  title: 'Viz/AssetGroupTreemap',
  component: AssetGroupTreemap,
  parameters: {
    layout: 'padded',
    a11y: { config: { rules: [{ id: 'color-contrast', enabled: true }] } },
    chromatic: { viewports: [375, 1280] },
  },
  tags: ['autodocs'],
};
export default meta;

type Story = StoryObj<typeof AssetGroupTreemap>;

const groups = [
  { name: 'Launch Push', spend: 5200, roas: 1.8 },
  { name: 'Evergreen', spend: 3100, roas: 1.1 },
  { name: 'Remarket', spend: 1800, roas: 0.9 },
  { name: 'Prospecting', spend: 900, roas: 2.3 },
  { name: 'Holiday Burst', spend: 2400, roas: 0.4 },
];

export const Default: Story = {
  args: {
    data: groups,
    ariaLabel: 'Performance Max asset groups by spend',
    currency: 'JMD',
  },
};

export const Loading: Story = {
  args: {
    data: [],
    isLoading: true,
    ariaLabel: 'Performance Max asset groups by spend',
  },
};

export const Empty: Story = {
  args: {
    data: [],
    ariaLabel: 'Performance Max asset groups by spend',
    emptyReasonCode: 'no_pmax_groups',
  },
};

export const DominantSlice: Story = {
  args: {
    data: [
      { name: 'Monster Campaign', spend: 80000, roas: 1.6 },
      { name: 'Runner Up', spend: 2000, roas: 0.9 },
      { name: 'Long Tail', spend: 400, roas: 0.3 },
    ],
    ariaLabel: 'Performance Max asset groups (dominant slice)',
  },
};
