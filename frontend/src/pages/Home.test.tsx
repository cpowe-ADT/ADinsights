import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, vi } from 'vitest';

import { ThemeProvider } from '../components/ThemeProvider';
import Home from './Home';

vi.mock('../lib/recentDashboards', () => ({
  fetchRecentDashboards: vi.fn(),
}));

import { fetchRecentDashboards } from '../lib/recentDashboards';

const fetchRecentDashboardsMock = vi.mocked(fetchRecentDashboards);
const authMock = vi.hoisted(() => ({
  user: { email: 'admin@example.com', roles: ['ADMIN'] },
}));

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => authMock,
}));

const routerFuture = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const;

describe('Home', () => {
  beforeEach(() => {
    fetchRecentDashboardsMock.mockClear();
    fetchRecentDashboardsMock.mockResolvedValue([]);
    authMock.user = { email: 'admin@example.com', roles: ['ADMIN'] };
  });

  const renderHome = () =>
    render(
      <ThemeProvider>
        <MemoryRouter future={routerFuture}>
          <Home />
        </MemoryRouter>
      </ThemeProvider>,
    );

  it('renders the quick action shortcuts', async () => {
    renderHome();
    await waitFor(() => expect(fetchRecentDashboardsMock).toHaveBeenCalled());

    const quickActionsHeading = screen.getByRole('heading', { name: /quick actions/i });
    const quickActionsSection = quickActionsHeading.closest('section');
    expect(quickActionsSection).not.toBeNull();
    const quickActionButtons = [
      within(quickActionsSection as HTMLElement).getByRole('button', {
        name: /create dashboard/i,
      }),
      within(quickActionsSection as HTMLElement).getByRole('button', { name: /view campaigns/i }),
      within(quickActionsSection as HTMLElement).getByRole('button', { name: /open map/i }),
      within(quickActionsSection as HTMLElement).getByRole('button', {
        name: /connect socials/i,
      }),
    ];

    quickActionButtons.forEach((button) => {
      expect(button).toBeInTheDocument();
    });
  });

  it('hides create dashboard actions for viewer-only users', async () => {
    authMock.user = { email: 'viewer@example.com', roles: ['VIEWER'] };
    renderHome();
    await waitFor(() => expect(fetchRecentDashboardsMock).toHaveBeenCalled());

    expect(screen.queryByRole('button', { name: /create dashboard/i })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /view campaigns/i })).toBeInTheDocument();
  });

  it('allows keyboard navigation through quick action cards', async () => {
    const user = userEvent.setup();
    renderHome();
    await waitFor(() => expect(fetchRecentDashboardsMock).toHaveBeenCalled());

    const quickActionsHeading = screen.getByRole('heading', { name: /quick actions/i });
    const quickActionsSection = quickActionsHeading.closest('section');
    expect(quickActionsSection).not.toBeNull();
    const quickActionButtons = [
      within(quickActionsSection as HTMLElement).getByRole('button', {
        name: /create dashboard/i,
      }),
      within(quickActionsSection as HTMLElement).getByRole('button', { name: /view campaigns/i }),
      within(quickActionsSection as HTMLElement).getByRole('button', { name: /open map/i }),
      within(quickActionsSection as HTMLElement).getByRole('button', {
        name: /connect socials/i,
      }),
    ];

    quickActionButtons[0]?.focus();
    expect(quickActionButtons[0]).toHaveFocus();

    await user.tab();
    expect(quickActionButtons[1]).toHaveFocus();

    await user.tab();
    expect(quickActionButtons[2]).toHaveFocus();

    await user.tab();
    expect(quickActionButtons[3]).toHaveFocus();
  });

  it('renders a theme toggle and updates root theme markers', async () => {
    const user = userEvent.setup();
    renderHome();
    await waitFor(() => expect(fetchRecentDashboardsMock).toHaveBeenCalled());

    const themeToggle = screen.getByRole('button', { name: /dark mode|light mode/i });
    expect(themeToggle).toBeInTheDocument();

    await user.click(themeToggle);
    expect(document.documentElement.classList.contains('theme-dark')).toBe(true);
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');

    await user.click(themeToggle);
    expect(document.documentElement.classList.contains('theme-light')).toBe(true);
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
  });
});
