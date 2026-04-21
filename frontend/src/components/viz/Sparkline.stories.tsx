import type { Meta, StoryObj } from '@storybook/react';

import Sparkline from './Sparkline';

const meta: Meta<typeof Sparkline> = {
  title: 'Viz/Sparkline',
  component: Sparkline,
  parameters: {
    layout: 'padded',
    a11y: { config: { rules: [{ id: 'color-contrast', enabled: true }] } },
    chromatic: { viewports: [375, 1280] },
  },
  tags: ['autodocs'],
};
export default meta;

type Story = StoryObj<typeof Sparkline>;

const makeSeries = (values: number[]) =>
  values.map((value, i) => ({ date: `d${i}`, value }));

export const Default: Story = {
  args: {
    data: makeSeries([12, 14, 13, 17, 19, 21, 24]),
    ariaLabel: 'Spend trend (last 7 days)',
  },
};

export const Flat: Story = {
  args: {
    data: makeSeries([10, 10, 10, 10, 10, 10, 10]),
    ariaLabel: 'Impressions (flat)',
  },
};

export const Rising: Story = {
  args: {
    data: makeSeries([1, 2, 3, 5, 8, 13, 21]),
    ariaLabel: 'Conversions (rising)',
  },
};

export const Falling: Story = {
  args: {
    data: makeSeries([20, 18, 14, 10, 7, 5, 4]),
    ariaLabel: 'Cost per conversion (falling)',
  },
};

export const DarkTheme: Story = {
  args: {
    data: makeSeries([12, 14, 13, 17, 19, 21, 24]),
    ariaLabel: 'Spend trend (last 7 days)',
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
