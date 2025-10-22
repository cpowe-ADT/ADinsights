import type { Meta, StoryObj } from '@storybook/react';
import { useEffect, type ReactNode } from 'react';

import FilterBar from './FilterBar';
import type { FilterBarState } from './FilterBar';
import { useTheme } from './ThemeProvider';

const defaultState: FilterBarState = {
  dateRange: '7d',
  customRange: {
    start: '2025-01-01',
    end: '2025-01-07',
  },
  channels: ['Meta Ads', 'Google Ads'],
  campaignQuery: '',
};

const ThemeWrapper = ({ theme, children }: { theme: 'light' | 'dark'; children: ReactNode }) => {
  const { setTheme } = useTheme();

  useEffect(() => {
    setTheme(theme);
  }, [setTheme, theme]);

  return <>{children}</>;
};

const meta: Meta<typeof FilterBar> = {
  title: 'Components/FilterBar',
  component: FilterBar,
  args: {
    availableChannels: ['Meta Ads', 'Google Ads', 'LinkedIn', 'TikTok'],
    defaultState,
  },
};

export default meta;

type Story = StoryObj<typeof FilterBar>;

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
