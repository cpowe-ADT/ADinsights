import type { Meta, StoryObj } from '@storybook/react';

import EmptyState from '../EmptyState';
import VizEmptyIcon from './VizEmptyIcon';

/**
 * Viz-kit presentation wrapper around the canonical `EmptyState` from
 * `components/EmptyState.tsx`. The primitive already satisfies the FP-CC-01
 * `reasonCode` contract, so this story file just exercises the reason codes
 * most commonly emitted by viz primitives.
 */
const meta: Meta<typeof EmptyState> = {
  title: 'Viz/EmptyState',
  component: EmptyState,
  parameters: {
    layout: 'padded',
    a11y: { config: { rules: [{ id: 'color-contrast', enabled: true }] } },
    chromatic: { viewports: [375, 1280] },
  },
  tags: ['autodocs'],
};
export default meta;

type Story = StoryObj<typeof EmptyState>;

export const NoAccounts: Story = {
  args: {
    icon: <VizEmptyIcon />,
    title: 'No ad accounts connected',
    message: 'Connect Meta or Google to start pulling live data.',
    reasonCode: 'no_accounts',
    actionLabel: 'Connect account',
    onAction: () => {},
  },
};

export const NoData: Story = {
  args: {
    icon: <VizEmptyIcon />,
    title: 'No data to display',
    message: 'There is no data for the selected range.',
    reasonCode: 'no_data_for_range',
  },
};

export const AdapterError: Story = {
  args: {
    icon: <VizEmptyIcon />,
    title: 'Adapter unavailable',
    message: 'The dashboard could not reach its data adapter. Retry or contact support.',
    reasonCode: 'adapter_error',
    actionLabel: 'Retry',
    onAction: () => {},
    secondaryActionLabel: 'Contact support',
    onSecondaryAction: () => {},
  },
};

export const NoDataForScope: Story = {
  args: {
    icon: <VizEmptyIcon />,
    title: 'No data for this scope',
    message: 'Try loosening your filters or switching account.',
    reasonCode: 'no_data_for_scope',
  },
};
