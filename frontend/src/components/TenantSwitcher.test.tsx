import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'jest-axe';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { AuthContextValue } from '../auth/AuthContext';
import type { TenantOption } from '../lib/tenants';

import TenantSwitcher from './TenantSwitcher';

vi.mock('../lib/tenants', () => ({
  loadTenants: vi.fn(),
}));

import { loadTenants } from '../lib/tenants';

const loadTenantsMock = vi.mocked(loadTenants);

const setActiveTenantMock = vi.fn();
const logoutMock = vi.fn();
const loginMock = vi.fn();

const authState: AuthContextValue = {
  status: 'authenticated',
  isAuthenticated: true,
  accessToken: 'token',
  tenantId: 'demo',
  user: undefined,
  error: undefined,
  login: loginMock,
  logout: logoutMock,
  setActiveTenant: setActiveTenantMock,
  statusMessage: undefined,
};

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => authState,
}));

const loadAllMock = vi.fn();

let dashboardState = {
  activeTenantId: 'demo',
  activeTenantLabel: 'Demo Retail Co.',
  loadAll: loadAllMock,
};

const selectDashboardState = <T,>(selector: (state: typeof dashboardState) => T) =>
  selector(dashboardState);
const mockUseDashboardStore = vi.fn(selectDashboardState);

vi.mock('../state/useDashboardStore', () => ({
  __esModule: true,
  default: (selector: (state: typeof dashboardState) => unknown) => mockUseDashboardStore(selector),
}));

const tenantFixtures: TenantOption[] = [
  { id: 'demo', name: 'Demo Retail Co.', status: 'active' },
  { id: 'jam-market', name: 'Jamaica Marketplaces', status: 'active' },
  { id: 'meta-latam', name: 'Meta LATAM Sandbox', status: 'inactive' },
];

beforeEach(() => {
  dashboardState = {
    activeTenantId: 'demo',
    activeTenantLabel: 'Demo Retail Co.',
    loadAll: loadAllMock,
  };
  authState.tenantId = 'demo';
  authState.setActiveTenant = setActiveTenantMock;
  setActiveTenantMock.mockReset();
  loadAllMock.mockReset();
  loadAllMock.mockResolvedValue(undefined);
  mockUseDashboardStore.mockClear();
  loadTenantsMock.mockResolvedValue(tenantFixtures);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('TenantSwitcher', () => {
  it('supports keyboard navigation to change tenants', async () => {
    const user = userEvent.setup();
    render(<TenantSwitcher />);

    const button = await screen.findByRole('button', { name: /demo retail co\./i });
    await user.click(button);

    const listbox = await screen.findByRole('listbox');
    expect(listbox).toBeInTheDocument();
    await waitFor(() => expect(listbox).toHaveFocus());

    await user.keyboard('{ArrowDown}{ArrowDown}{Enter}');

    await waitFor(() => {
      expect(setActiveTenantMock).toHaveBeenCalledWith('meta-latam', 'Meta LATAM Sandbox');
    });
    expect(loadAllMock).toHaveBeenCalledWith('meta-latam', { force: true });
    await waitFor(() => expect(button).toHaveFocus());
  });

  it('announces API failures via aria-live region', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    loadTenantsMock.mockRejectedValueOnce(new Error('Network error'));

    render(<TenantSwitcher />);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Network error');

    const liveRegion = screen.getByRole('status', { hidden: true });
    expect(liveRegion).toHaveTextContent('Unable to load tenants. Network error');

    consoleErrorSpy.mockRestore();
  });

  it('announces tenant changes through aria-live', async () => {
    const user = userEvent.setup();
    render(<TenantSwitcher />);

    const button = await screen.findByRole('button', { name: /demo retail co\./i });
    await user.click(button);
    const listbox = await screen.findByRole('listbox');
    await waitFor(() => expect(listbox).toHaveFocus());
    await user.keyboard('{ArrowDown}{Enter}');

    const liveRegion = screen.getByRole('status', { hidden: true });
    await waitFor(() => {
      expect(liveRegion.textContent).toContain('Switched to Jamaica Marketplaces');
    });
  });

  it('passes axe accessibility checks', async () => {
    const { container } = render(<TenantSwitcher />);
    await screen.findByRole('button', { name: /demo retail co\./i });

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
