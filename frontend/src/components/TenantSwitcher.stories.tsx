import type { Meta, StoryObj } from '@storybook/react';
import { useEffect, useMemo, useState, type ReactNode } from 'react';

import { AuthContext, type AuthContextValue } from '../auth/AuthContext';
import type { TenantOption } from '../lib/tenants';
import useDashboardStore from '../state/useDashboardStore';
import TenantSwitcher from './TenantSwitcher';
import { ThemeProvider, useTheme } from './ThemeProvider';

const tenantFixtures: TenantOption[] = [
  { id: 'demo', name: 'Demo Retail Co.', status: 'active' },
  { id: 'jam-market', name: 'Jamaica Marketplaces', status: 'active' },
  { id: 'meta-latam', name: 'Meta LATAM Sandbox', status: 'inactive' },
];

const FetchMock = ({ children }: { children: ReactNode }) => {
  useEffect(() => {
    const originalFetch = window.fetch.bind(window);

    window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
      if (url.includes('/tenants/') || url.endsWith('/mock/tenants.json')) {
        return new Response(JSON.stringify(tenantFixtures), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return originalFetch(input, init);
    };

    return () => {
      window.fetch = originalFetch;
    };
  }, []);

  return <>{children}</>;
};

const ThemeSetter = ({ theme, children }: { theme: 'light' | 'dark'; children: ReactNode }) => {
  const { setTheme } = useTheme();

  useEffect(() => {
    setTheme(theme);
  }, [setTheme, theme]);

  return <>{children}</>;
};

const StoryAuthProvider = ({ children }: { children: ReactNode }) => {
  const [tenantId, setTenantId] = useState<string>(tenantFixtures[0].id);

  useEffect(() => {
    const match = tenantFixtures.find((tenant) => tenant.id === tenantId);
    useDashboardStore.setState({
      activeTenantId: tenantId,
      activeTenantLabel: match?.name,
      lastLoadedTenantId: tenantId,
    });
  }, [tenantId]);

  useEffect(() => {
    const originalLoadAll = useDashboardStore.getState().loadAll;
    useDashboardStore.setState({
      loadAll: async (nextTenantId?: string) => {
        const resolvedId = nextTenantId ?? tenantId;
        const match = tenantFixtures.find((tenant) => tenant.id === resolvedId);
        useDashboardStore.setState({
          activeTenantId: resolvedId,
          activeTenantLabel: match?.name,
          lastLoadedTenantId: resolvedId,
        });
      },
    });

    return () => {
      useDashboardStore.setState({ loadAll: originalLoadAll });
    };
  }, [tenantId]);

  const contextValue = useMemo<AuthContextValue>(() => ({
    status: 'authenticated',
    isAuthenticated: true,
    accessToken: 'story-token',
    tenantId,
    user: { email: 'analyst@example.com' },
    error: undefined,
    login: async () => undefined,
    logout: () => undefined,
    setActiveTenant: (nextTenantId?: string, label?: string) => {
      if (!nextTenantId) {
        return;
      }
      setTenantId(nextTenantId);
      useDashboardStore.setState({
        activeTenantId: nextTenantId,
        activeTenantLabel: label ?? tenantFixtures.find((tenant) => tenant.id === nextTenantId)?.name,
        lastLoadedTenantId: nextTenantId,
      });
    },
    statusMessage: undefined,
  }), [tenantId]);

  return <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>;
};

const Providers = ({ children, theme }: { children: ReactNode; theme: 'light' | 'dark' }) => (
  <ThemeProvider>
    <ThemeSetter theme={theme}>
      <FetchMock>
        <StoryAuthProvider>{children}</StoryAuthProvider>
      </FetchMock>
    </ThemeSetter>
  </ThemeProvider>
);

const meta: Meta<typeof TenantSwitcher> = {
  title: 'Components/TenantSwitcher',
  component: TenantSwitcher,
  decorators: [
    (StoryComponent) => (
      <Providers theme="light">
        <StoryComponent />
      </Providers>
    ),
  ],
  parameters: {
    layout: 'centered',
  },
};

export default meta;

type Story = StoryObj<typeof TenantSwitcher>;

export const Light: Story = {};

export const Dark: Story = {
  decorators: [
    (StoryComponent) => (
      <Providers theme="dark">
        <StoryComponent />
      </Providers>
    ),
  ],
};
