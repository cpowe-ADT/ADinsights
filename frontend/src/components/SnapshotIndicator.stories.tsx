import type { Meta, StoryObj } from '@storybook/react';
import { useEffect, type ReactNode } from 'react';

import SnapshotIndicator from './SnapshotIndicator';
import { useTheme } from './ThemeProvider';

const ThemeWrapper = ({ theme, children }: { theme: 'light' | 'dark'; children: ReactNode }) => {
  const { setTheme } = useTheme();

  useEffect(() => {
    setTheme(theme);
  }, [setTheme, theme]);

  return <>{children}</>;
};

const meta: Meta<typeof SnapshotIndicator> = {
  title: 'Components/SnapshotIndicator',
  component: SnapshotIndicator,
  parameters: {
    layout: 'centered',
  },
  args: {
    label: 'Updated 5 minutes ago',
    tone: 'fresh',
  },
};

export default meta;

type Story = StoryObj<typeof SnapshotIndicator>;

export const Fresh: Story = {};

export const Stale: Story = {
  args: {
    label: 'Updated 2 hours ago',
    tone: 'stale',
  },
};

export const Pending: Story = {
  args: {
    label: 'Waiting for live snapshot…',
    tone: 'pending',
  },
};

export const Demo: Story = {
  args: {
    label: 'Demo dataset active',
    tone: 'demo',
  },
};

export const Dark: Story = {
  args: {
    label: 'Updated 5 minutes ago',
    tone: 'fresh',
  },
  decorators: [
    (StoryComponent) => (
      <ThemeWrapper theme="dark">
        <StoryComponent />
      </ThemeWrapper>
    ),
  ],
};
