import type { Meta, StoryObj } from '@storybook/react';

import KpiTile from './KpiTile';

const meta: Meta<typeof KpiTile> = {
  title: 'Viz/KpiTile',
  component: KpiTile,
  parameters: {
    layout: 'padded',
    a11y: { config: { rules: [{ id: 'color-contrast', enabled: true }] } },
    chromatic: { viewports: [375, 1280] },
  },
  tags: ['autodocs'],
};
export default meta;

type Story = StoryObj<typeof KpiTile>;

const trend = [12, 18, 14, 22, 19, 26, 31];

export const Default: Story = {
  args: {
    label: 'Spend',
    value: 24850,
    format: 'currency',
    currency: 'JMD',
    change: 0.124,
    trend,
  },
};

export const Loading: Story = {
  args: {
    label: 'Spend',
    value: null,
    isLoading: true,
  },
};

export const Empty: Story = {
  args: {
    label: 'Spend',
    value: null,
    format: 'currency',
    currency: 'JMD',
    reasonCode: 'no_data_for_range',
  },
};

export const WithDeltaUp: Story = {
  args: {
    label: 'Conversions',
    value: 512,
    format: 'number',
    change: 0.23,
    trend,
  },
};

export const WithDeltaDown: Story = {
  args: {
    label: 'CTR',
    value: 0.034,
    format: 'percent',
    change: -0.087,
    trend: [3.1, 3.3, 3.0, 2.8, 2.6, 2.4, 2.5],
  },
};

export const Faded: Story = {
  args: {
    label: 'Spend',
    value: 24850,
    format: 'currency',
    currency: 'JMD',
    change: 0.124,
    trend,
    isFaded: true,
  },
};

export const DarkTheme: Story = {
  args: {
    label: 'Spend',
    value: 24850,
    format: 'currency',
    currency: 'JMD',
    change: 0.124,
    trend,
  },
  decorators: [
    (StoryComponent) => (
      <div
        data-theme="dark"
        style={{ background: 'var(--color-surface-card)', padding: 16 }}
      >
        <StoryComponent />
      </div>
    ),
  ],
};
