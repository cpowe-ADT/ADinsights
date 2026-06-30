import type { Meta, StoryObj } from '@storybook/react';

import DistributionBar from './DistributionBar';

const meta: Meta<typeof DistributionBar> = {
  title: 'Viz/DistributionBar',
  component: DistributionBar,
  parameters: {
    layout: 'padded',
    a11y: { config: { rules: [{ id: 'color-contrast', enabled: true }] } },
    chromatic: { viewports: [375, 1280] },
  },
  tags: ['autodocs'],
};
export default meta;

type Story = StoryObj<typeof DistributionBar>;

const parishData = [
  { label: 'Kingston', value: 5200 },
  { label: 'St. Andrew', value: 4100 },
  { label: 'St. Catherine', value: 3300 },
  { label: 'Clarendon', value: 2400 },
  { label: 'Manchester', value: 1800 },
];

export const Default: Story = {
  args: {
    data: parishData,
    ariaLabel: 'Spend by parish',
    yFormat: 'currency',
  },
};

export const Loading: Story = {
  args: {
    data: [],
    isLoading: true,
    ariaLabel: 'Spend by parish',
  },
};

export const Empty: Story = {
  args: {
    data: [],
    ariaLabel: 'Spend by parish',
    emptyReasonCode: 'no_data_for_range',
  },
};

export const Horizontal: Story = {
  args: {
    data: parishData,
    orientation: 'horizontal',
    ariaLabel: 'Spend by parish (horizontal)',
    yFormat: 'currency',
  },
};

export const Vertical: Story = {
  args: {
    data: parishData,
    orientation: 'vertical',
    ariaLabel: 'Spend by parish (vertical)',
    yFormat: 'currency',
  },
};

export const WithPercent: Story = {
  args: {
    data: parishData,
    showPercent: true,
    ariaLabel: 'Spend share by parish',
    yFormat: 'currency',
  },
};

export const DarkTheme: Story = {
  args: {
    data: parishData,
    ariaLabel: 'Spend by parish',
    yFormat: 'currency',
  },
  decorators: [
    (StoryComponent) => (
      <div data-theme="dark" style={{ background: 'var(--color-surface-card)', padding: 16 }}>
        <StoryComponent />
      </div>
    ),
  ],
};
