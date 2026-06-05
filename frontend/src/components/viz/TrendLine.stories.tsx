import type { Meta, StoryObj } from '@storybook/react';

import TrendLine from './TrendLine';
import type { TrendLinePoint, TrendLineSeries } from './TrendLine';

const meta: Meta<typeof TrendLine> = {
  title: 'Viz/TrendLine',
  component: TrendLine,
  parameters: {
    layout: 'padded',
    a11y: { config: { rules: [{ id: 'color-contrast', enabled: true }] } },
    chromatic: { viewports: [375, 1280] },
  },
  tags: ['autodocs'],
};
export default meta;

type Story = StoryObj<typeof TrendLine>;

const days = ['Apr 01', 'Apr 02', 'Apr 03', 'Apr 04', 'Apr 05', 'Apr 06', 'Apr 07'];

const singleSeriesData: TrendLinePoint[] = days.map((d, i) => ({
  date: d,
  spend: 1000 + i * 120 + (i % 2 === 0 ? 80 : -40),
}));

const multiSeriesData: TrendLinePoint[] = days.map((d, i) => ({
  date: d,
  spend: 1000 + i * 120,
  conversions: 30 + i * 4,
  ctr: 0.02 + i * 0.003,
}));

const singleSeries: TrendLineSeries[] = [{ key: 'spend', label: 'Spend' }];

const multiSeries: TrendLineSeries[] = [
  { key: 'spend', label: 'Spend' },
  { key: 'conversions', label: 'Conversions' },
  { key: 'ctr', label: 'CTR', dashed: true },
];

export const Default: Story = {
  args: {
    data: singleSeriesData,
    series: singleSeries,
    ariaLabel: 'Daily spend trend',
    yFormat: 'currency',
  },
};

export const Loading: Story = {
  args: {
    data: [],
    series: singleSeries,
    isLoading: true,
    ariaLabel: 'Daily spend trend',
  },
};

export const Empty: Story = {
  args: {
    data: [],
    series: singleSeries,
    ariaLabel: 'Daily spend trend',
    emptyReasonCode: 'no_data_for_range',
  },
};

export const SingleSeries: Story = {
  args: {
    data: singleSeriesData,
    series: singleSeries,
    ariaLabel: 'Daily spend trend',
    yFormat: 'currency',
  },
};

export const MultiSeries: Story = {
  args: {
    data: multiSeriesData,
    series: multiSeries,
    ariaLabel: 'Daily performance across spend, conversions, and CTR',
    yFormat: 'number',
  },
};

export const DualAxis: Story = {
  args: {
    data: multiSeriesData,
    series: [
      { key: 'spend', label: 'Spend', yAxis: 'left' },
      { key: 'ctr', label: 'CTR', yAxis: 'right', dashed: true },
    ],
    rightYFormat: 'percent',
    yFormat: 'currency',
    ariaLabel: 'Spend vs. CTR dual axis',
  },
};

export const WithPeerAvg: Story = {
  args: {
    data: singleSeriesData,
    series: singleSeries,
    peerData: days.map((d, i) => ({ date: d, value: 900 + i * 95 })),
    ariaLabel: 'Spend vs. peer average',
    yFormat: 'currency',
  },
};

export const DarkTheme: Story = {
  args: {
    data: multiSeriesData,
    series: multiSeries,
    ariaLabel: 'Daily performance trend',
  },
  decorators: [
    (StoryComponent) => (
      <div data-theme="dark" style={{ background: 'var(--color-surface-card)', padding: 16 }}>
        <StoryComponent />
      </div>
    ),
  ],
};
