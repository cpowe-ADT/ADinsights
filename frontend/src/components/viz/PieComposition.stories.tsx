import type { Meta, StoryObj } from '@storybook/react';

import PieComposition from './PieComposition';

const meta: Meta<typeof PieComposition> = {
  title: 'Viz/PieComposition',
  component: PieComposition,
  parameters: {
    layout: 'padded',
    a11y: { config: { rules: [{ id: 'color-contrast', enabled: true }] } },
    chromatic: { viewports: [375, 1280] },
  },
  tags: ['autodocs'],
};
export default meta;

type Story = StoryObj<typeof PieComposition>;

const deviceData = [
  { label: 'Mobile', value: 6800 },
  { label: 'Desktop', value: 2400 },
  { label: 'Tablet', value: 800 },
];

export const Default: Story = {
  args: {
    data: deviceData,
    ariaLabel: 'Spend by device',
    yFormat: 'currency',
  },
};

export const Loading: Story = {
  args: {
    data: [],
    isLoading: true,
    ariaLabel: 'Spend by device',
  },
};

export const Empty: Story = {
  args: {
    data: [],
    emptyReasonCode: 'no_data_for_range',
    ariaLabel: 'Spend by device',
  },
};

export const Donut: Story = {
  args: {
    data: deviceData,
    innerRadius: 60,
    ariaLabel: 'Spend by device (donut)',
    yFormat: 'currency',
  },
};

export const Pie: Story = {
  args: {
    data: deviceData,
    innerRadius: 0,
    ariaLabel: 'Spend by device (pie)',
    yFormat: 'currency',
  },
};

export const WithCenterLabel: Story = {
  args: {
    data: deviceData,
    innerRadius: 70,
    centerLabel: 'JMD 10,000',
    ariaLabel: 'Spend by device with total',
    yFormat: 'currency',
  },
};

export const DarkTheme: Story = {
  args: {
    data: deviceData,
    ariaLabel: 'Spend by device',
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
