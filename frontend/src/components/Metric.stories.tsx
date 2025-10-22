import type { Meta, StoryObj } from '@storybook/react';
import { useEffect, type ReactNode } from 'react';

import Metric from './Metric';
import { useTheme } from './ThemeProvider';

const ThemeWrapper = ({ theme, children }: { theme: 'light' | 'dark'; children: ReactNode }) => {
  const { setTheme } = useTheme();

  useEffect(() => {
    setTheme(theme);
  }, [setTheme, theme]);

  return <>{children}</>;
};

const meta: Meta<typeof Metric> = {
  title: 'Components/Metric',
  component: Metric,
  parameters: {
    layout: 'centered',
  },
  args: {
    label: 'Spend',
    value: '$24.2K',
    delta: '+12.3%',
    deltaDirection: 'up',
    hint: 'Compared to previous period',
  },
};

export default meta;

type Story = StoryObj<typeof Metric>;

export const Light: Story = {};

export const Dark: Story = {
  decorators: [
    (StoryComponent) => (
      <ThemeWrapper theme="dark">
        <StoryComponent />
      </ThemeWrapper>
    ),
  ],
};

export const WithTrend: Story = {
  args: {
    trend: [12, 14, 16, 15, 18, 21, 24],
  },
};

export const WarningBadge: Story = {
  args: {
    badge: 'Limited data',
    delta: '-2.1%',
    deltaDirection: 'down',
  },
  decorators: [
    (StoryComponent) => (
      <ThemeWrapper theme="dark">
        <StoryComponent />
      </ThemeWrapper>
    ),
  ],
};
