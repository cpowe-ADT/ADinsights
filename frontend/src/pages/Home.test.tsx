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

const routerFuture = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const;

describe('Home', () => {
  beforeEach(() => {
    fetchRecentDashboardsMock.mockClear();
    fetchRecentDashboardsMock.mockResolvedValue([]);
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
