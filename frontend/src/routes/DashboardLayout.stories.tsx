import type { Meta, StoryObj } from '@storybook/react';
import { Routes, Route } from 'react-router-dom';
import { useEffect, useRef, type ReactNode } from 'react';

import DashboardLayout from './DashboardLayout';
import { useTheme } from '../components/ThemeProvider';
import useDashboardStore from '../state/useDashboardStore';
import { useDatasetStore } from '../state/useDatasetStore';

const ThemeWrapper = ({ theme, children }: { theme: 'light' | 'dark'; children: ReactNode }) => {
  const { setTheme } = useTheme();

  useEffect(() => {
    setTheme(theme);
  }, [setTheme, theme]);

  return <>{children}</>;
};

const StoreBootstrap = ({ children }: { children: ReactNode }) => {
  const datasetSnapshot = useRef(useDatasetStore.getState());
  const dashboardSnapshot = useRef(useDashboardStore.getState());

  useEffect(() => {
    const initialDatasetState = datasetSnapshot.current;
    const initialDashboardState = dashboardSnapshot.current;

    useDatasetStore.setState({
      adapters: ['fake', 'warehouse'],
      mode: 'live',
      status: 'loaded',
      error: undefined,
      source: 'warehouse',
    });

    useDashboardStore.setState((state) => ({
      ...state,
      selectedMetric: 'spend',
      loadAll: async () => undefined,
      campaign: { status: 'loaded' },
      creative: { status: 'loaded' },
      budget: { status: 'loaded' },
      parish: { status: 'loaded' },
    }));

    return () => {
      useDatasetStore.setState(initialDatasetState, true);
      useDashboardStore.setState(initialDashboardState, true);
    };
  }, []);

  return <>{children}</>;
};

const PlaceholderContent = () => (
  <div
    style={{
      display: 'grid',
      gap: 'var(--space-4)',
      paddingBlock: 'var(--space-4)',
    }}
  >
    <section
      style={{
        background: 'var(--color-surface-card)',
        border: '1px solid var(--color-border-subtle)',
        borderRadius: 'var(--radius-md)',
        padding: 'var(--space-5)',
        boxShadow: 'var(--shadow-subtle)',
      }}
    >
      <h2 style={{ margin: 0 }}>Campaign overview</h2>
      <p style={{ marginBottom: 0 }}>Sample data for Chromatic baselines.</p>
    </section>
    <section
      style={{
        background: 'var(--color-surface-card)',
        border: '1px solid var(--color-border-subtle)',
        borderRadius: 'var(--radius-md)',
        padding: 'var(--space-5)',
        boxShadow: 'var(--shadow-subtle)',
      }}
    >
      <h3 style={{ margin: 0 }}>Recent activity</h3>
      <ul style={{ margin: 'var(--space-3) 0 0', paddingLeft: 'var(--space-5)' }}>
        <li>Sync succeeded 5 minutes ago</li>
        <li>ROAS improved by 8% week over week</li>
      </ul>
    </section>
  </div>
);

const meta: Meta<typeof DashboardLayout> = {
  title: 'Routes/DashboardLayout',
  component: DashboardLayout,
  parameters: {
    layout: 'fullscreen',
    initialEntries: ['/dashboards/campaigns'],
  },
};

export default meta;

type Story = StoryObj<typeof DashboardLayout>;

const renderLayout = () => (
  <StoreBootstrap>
    <Routes>
      <Route path="/dashboards/*" element={<DashboardLayout />}>
        <Route index element={<PlaceholderContent />} />
      </Route>
    </Routes>
  </StoreBootstrap>
);

export const Light: Story = {
  render: renderLayout,
};

export const Dark: Story = {
  render: () => (
    <ThemeWrapper theme="dark">
      {renderLayout()}
    </ThemeWrapper>
  ),
};
