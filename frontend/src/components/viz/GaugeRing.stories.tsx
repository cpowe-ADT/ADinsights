import type { Meta, StoryObj } from '@storybook/react';

import GaugeRing from './GaugeRing';

const meta: Meta<typeof GaugeRing> = {
  title: 'Viz/GaugeRing',
  component: GaugeRing,
  parameters: {
    layout: 'padded',
    a11y: { config: { rules: [{ id: 'color-contrast', enabled: true }] } },
    chromatic: { viewports: [375, 1280] },
  },
  tags: ['autodocs'],
};
export default meta;

type Story = StoryObj<typeof GaugeRing>;

export const Default: Story = {
  args: {
    value: 0.87,
    max: 1.2,
    label: 'Pacing',
    ariaLabel: 'Pacing 87%',
  },
};

export const Underdelivery: Story = {
  args: {
    value: 0.45,
    max: 1.2,
    label: 'Pacing',
    variant: 'warning',
    ariaLabel: 'Pacing 45%',
  },
};

export const OnTrack: Story = {
  args: {
    value: 1.0,
    max: 1.2,
    label: 'Pacing',
    variant: 'ok',
    ariaLabel: 'Pacing 100%',
  },
};

export const Overspend: Story = {
  args: {
    value: 1.15,
    max: 1.2,
    label: 'Pacing',
    variant: 'danger',
    ariaLabel: 'Pacing 115%',
  },
};

export const Loading: Story = {
  args: {
    value: 0,
    max: 1.2,
    label: 'Pacing',
    ariaLabel: 'Pacing',
    isLoading: true,
  },
};

export const Empty: Story = {
  args: {
    value: Number.NaN,
    max: 1.2,
    label: 'Pacing',
    ariaLabel: 'Pacing',
    emptyReasonCode: 'no_pacing_data',
  },
};

export const ExtremeOverspend: Story = {
  args: {
    value: 5,
    max: 1.5,
    label: 'Pacing',
    variant: 'danger',
    ariaLabel: 'Pacing 500%',
  },
};
