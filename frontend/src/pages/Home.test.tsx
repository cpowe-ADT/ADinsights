import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, vi } from 'vitest';

import Home from './Home';

vi.mock('../lib/recentDashboards', () => ({
  fetchRecentDashboards: vi.fn(),
}));

import { fetchRecentDashboards } from '../lib/recentDashboards';

const fetchRecentDashboardsMock = vi.mocked(fetchRecentDashboards);

const routerFuture = {
  v7_startTransition: true,
} as const;

describe('Home', () => {
  beforeEach(() => {
    fetchRecentDashboardsMock.mockClear();
    fetchRecentDashboardsMock.mockResolvedValue([]);
  });

  const renderHome = () =>
    render(
      <MemoryRouter future={routerFuture}>
        <Home />
      </MemoryRouter>,
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
    ];

    quickActionButtons[0]?.focus();
    expect(quickActionButtons[0]).toHaveFocus();

    await user.tab();
    expect(quickActionButtons[1]).toHaveFocus();

    await user.tab();
    expect(quickActionButtons[2]).toHaveFocus();
  });
});
