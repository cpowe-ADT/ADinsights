import type { Meta, StoryObj } from '@storybook/react';
import { useEffect } from 'react';

import DatasetToggle from './DatasetToggle';
import useDashboardStore from '../state/useDashboardStore';
import { useDatasetStore } from '../state/useDatasetStore';
import { demoTenants } from '../storyData/demoSnapshots';

type DatasetState = Partial<
  Pick<
    ReturnType<typeof useDatasetStore.getState>,
    'mode' | 'status' | 'adapters' | 'error' | 'source' | 'demoTenants' | 'demoTenantId'
  >
>;

interface StoryArgs {
  datasetState: DatasetState;
  label?: string;
}

const ensureDefaults = (state: DatasetState): DatasetState => ({
  adapters: ['warehouse', 'demo'],
  mode: 'live',
  status: 'loaded',
  error: undefined,
  source: 'warehouse',
  demoTenants,
  demoTenantId: demoTenants[0]?.id,
  ...state,
});

const DatasetStory = ({ datasetState }: StoryArgs) => {
  useEffect(() => {
    const datasetSnapshot = useDatasetStore.getState();
    const dashboardSnapshot = useDashboardStore.getState();

    useDatasetStore.setState(ensureDefaults(datasetState), true);
    useDashboardStore.setState(
      {
        ...dashboardSnapshot,
        activeTenantId: datasetState.demoTenantId ?? dashboardSnapshot.activeTenantId ?? demoTenants[0]?.id,
        loadAll: async () => undefined,
      },
      true,
    );

    return () => {
      useDatasetStore.setState(datasetSnapshot, true);
      useDashboardStore.setState(dashboardSnapshot, true);
    };
  }, [datasetState]);

  return <DatasetToggle />;
};

const meta: Meta<typeof DatasetStory> = {
  title: 'Components/DatasetToggle',
  component: DatasetStory,
  parameters: {
    layout: 'centered',
  },
  args: {
    datasetState: {},
  },
};

export default meta;

type Story = StoryObj<typeof DatasetStory>;

export const LiveAvailable: Story = {
  args: {
    datasetState: {
      mode: 'live',
      adapters: ['warehouse', 'demo'],
      status: 'loaded',
      source: 'warehouse',
    },
  },
};

export const DemoMode: Story = {
  args: {
    datasetState: {
      mode: 'dummy',
      adapters: ['warehouse', 'demo'],
      status: 'loaded',
      source: 'demo',
    },
  },
};

export const LoadingAdapters: Story = {
  args: {
    datasetState: {
      mode: 'live',
      adapters: [],
      status: 'loading',
      source: undefined,
    },
  },
};

export const ErrorState: Story = {
  args: {
    datasetState: {
      mode: 'live',
      adapters: [],
      status: 'loaded',
      source: undefined,
      error: 'Demo dataset unavailable. Please try again later.',
    },
  },
};
