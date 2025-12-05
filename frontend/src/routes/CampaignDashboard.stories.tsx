import type { Meta, StoryObj } from '@storybook/react';
import { useEffect, useMemo, useRef, type ReactNode } from 'react';

import CampaignDashboard from './CampaignDashboard';
import { AuthContext, type AuthContextValue } from '../auth/AuthContext';
import { useTheme } from '../components/ThemeProvider';
import useDashboardStore from '../state/useDashboardStore';
import { useDatasetStore } from '../state/useDatasetStore';
import {
  defaultDemoTenant,
  demoTenants,
  getDemoSnapshot,
  type DemoTenantKey,
} from '../storyData/demoSnapshots';

interface StoreBootstrapProps {
  tenantId: DemoTenantKey;
  datasetMode?: 'live' | 'dummy';
  snapshotVariant?: 'fresh' | 'stale' | 'pending';
  children: ReactNode;
}

const StoreBootstrap = ({ tenantId, datasetMode = 'dummy', snapshotVariant = 'fresh', children }: StoreBootstrapProps) => {
  const datasetSnapshot = useRef(useDatasetStore.getState());
  const dashboardSnapshot = useRef(useDashboardStore.getState());

  useEffect(() => {
    const originalFetch =
      window.fetch?.bind(window) ??
      ((input: RequestInfo | URL, init?: RequestInit) => fetch(input, init));

    const resolveUrl = (input: RequestInfo | URL): string => {
      if (typeof input === 'string') {
        return input;
      }
      if (input instanceof URL) {
        return input.toString();
      }
      if (
        typeof input === 'object' &&
        input !== null &&
        'url' in input &&
        typeof (input as { url?: unknown }).url === 'string'
      ) {
        return (input as Request).url;
      }
      return '';
    };

    window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = resolveUrl(input);
      if (url.includes('/analytics/parish-geometry/')) {
        return originalFetch('/jm_parishes.json', init);
      }
      return originalFetch(input, init);
    };

    return () => {
      window.fetch = originalFetch;
    };
  }, []);

  useEffect(() => {
    const initialDatasetState = datasetSnapshot.current;
    const initialDashboardState = dashboardSnapshot.current;

    return () => {
      useDatasetStore.setState(initialDatasetState, true);
      useDashboardStore.setState(initialDashboardState, true);
    };
  }, []);

  useEffect(() => {
    const snapshot = getDemoSnapshot(tenantId);
    const now = new Date();
    const snapshotAgeMinutes = snapshotVariant === 'stale' ? 120 : 5;
    const computedSnapshotGeneratedAt =
      snapshotVariant === 'pending'
        ? undefined
        : new Date(now.getTime() - snapshotAgeMinutes * 60 * 1000).toISOString();

    useDatasetStore.setState({
      adapters: ['warehouse', 'demo'],
      mode: datasetMode,
      status: 'loaded',
      error: undefined,
      source: datasetMode === 'live' ? 'warehouse' : 'demo',
      demoTenants,
      demoTenantId: snapshot.id,
    });

    useDashboardStore.setState((state) => ({
      ...state,
      activeTenantId: snapshot.id,
      activeTenantLabel: snapshot.label,
      lastLoadedTenantId: snapshot.id,
      lastSnapshotGeneratedAt: computedSnapshotGeneratedAt,
      selectedParish: undefined,
      selectedMetric: 'spend',
      loadAll: async () => undefined,
      campaign: { status: 'loaded', data: snapshot.metrics.campaign, error: undefined },
      creative: { status: 'loaded', data: snapshot.metrics.creative, error: undefined },
      budget: { status: 'loaded', data: snapshot.metrics.budget, error: undefined },
      parish: { status: 'loaded', data: snapshot.metrics.parish, error: undefined },
      metricsCache: {
        ...state.metricsCache,
        [`${snapshot.id}::dummy`]: {
          campaign: snapshot.metrics.campaign,
          creative: snapshot.metrics.creative,
          budget: snapshot.metrics.budget,
          parish: snapshot.metrics.parish,
          tenantId: snapshot.id,
          currency: snapshot.metrics.campaign.summary.currency,
          snapshotGeneratedAt: computedSnapshotGeneratedAt,
        },
      },
    }));
  }, [tenantId, datasetMode, snapshotVariant]);

  return <>{children}</>;
};

interface DashboardStoryProps {
  tenantId: DemoTenantKey;
  theme: 'light' | 'dark';
  datasetMode?: 'live' | 'dummy';
  snapshotVariant?: 'fresh' | 'stale' | 'pending';
}

const DashboardStory = ({ tenantId, theme, datasetMode = 'dummy', snapshotVariant = 'fresh' }: DashboardStoryProps) => {
  const { setTheme } = useTheme();
  const snapshot = getDemoSnapshot(tenantId);

  useEffect(() => {
    setTheme(theme);
  }, [setTheme, theme]);

  const authValue = useMemo<AuthContextValue>(() => {
    const setTenant = useDashboardStore.getState().setActiveTenant;
    const setDemoTenantId = useDatasetStore.getState().setDemoTenantId;

    return {
      status: 'authenticated',
      isAuthenticated: true,
      accessToken: 'story-token',
      tenantId: snapshot.id,
      user: { email: 'analyst@example.com' },
      login: async () => undefined,
      logout: () => undefined,
      setActiveTenant: (nextTenantId?: string, nextTenantLabel?: string) => {
        setTenant(nextTenantId, nextTenantLabel);
        if (nextTenantId) {
          setDemoTenantId(nextTenantId);
        }
      },
      statusMessage: undefined,
    };
  }, [snapshot.id, snapshot.label]);

  return (
    <AuthContext.Provider value={authValue}>
      <StoreBootstrap tenantId={snapshot.id} datasetMode={datasetMode} snapshotVariant={snapshotVariant}>
        <CampaignDashboard />
      </StoreBootstrap>
    </AuthContext.Provider>
  );
};

const meta: Meta<typeof DashboardStory> = {
  title: 'Routes/CampaignDashboard',
  component: DashboardStory,
  args: {
    tenantId: defaultDemoTenant,
    theme: 'light',
  },
  argTypes: {
    tenantId: {
      control: 'select',
      options: demoTenants.map((tenant) => tenant.id),
    },
    theme: {
      control: 'inline-radio',
      options: ['light', 'dark'],
    },
  },
  parameters: {
    layout: 'fullscreen',
    chromatic: { viewports: [375, 1280] },
  },
};

export default meta;

type Story = StoryObj<typeof DashboardStory>;

export const BankOfJamaica: Story = {
  args: {
    tenantId: 'bank-of-jamaica',
    theme: 'light',
  },
};

export const GraceKennedy: Story = {
  args: {
    tenantId: 'grace-kennedy',
    theme: 'light',
  },
};

export const JDIC: Story = {
  args: {
    tenantId: 'jdic',
    theme: 'light',
  },
};

export const Dark: Story = {
  args: {
    tenantId: 'bank-of-jamaica',
    theme: 'dark',
  },
};

export const LiveFresh: Story = {
  args: {
    tenantId: 'bank-of-jamaica',
    theme: 'light',
    datasetMode: 'live',
    snapshotVariant: 'fresh',
  },
};

export const LiveStale: Story = {
  args: {
    tenantId: 'bank-of-jamaica',
    theme: 'light',
    datasetMode: 'live',
    snapshotVariant: 'stale',
  },
};

export const WaitingForSnapshot: Story = {
  args: {
    tenantId: 'bank-of-jamaica',
    theme: 'light',
    datasetMode: 'live',
    snapshotVariant: 'pending',
  },
};
