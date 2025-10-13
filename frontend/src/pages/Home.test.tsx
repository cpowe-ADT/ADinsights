import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

import Home from './Home';

describe('Home', () => {
  const renderHome = () =>
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );

  it('renders the quick action shortcuts', () => {
    renderHome();

    const quickActions = [
      screen.getByRole('button', { name: /connect data sources/i }),
      screen.getByRole('button', { name: /create dashboard/i }),
      screen.getByRole('button', { name: /upload csv/i }),
      screen.getByRole('button', { name: /view docs/i }),
    ];

    quickActions.forEach((button) => {
      expect(button).toBeInTheDocument();
    });
  });

  it('allows keyboard navigation through quick action cards', async () => {
    const user = userEvent.setup();
    renderHome();

    const quickActionButtons = [
      screen.getByRole('button', { name: /connect data sources/i }),
      screen.getByRole('button', { name: /create dashboard/i }),
      screen.getByRole('button', { name: /upload csv/i }),
      screen.getByRole('button', { name: /view docs/i }),
    ];

    // First two tabs move through hero buttons before the quick actions list.
    await user.tab();
    await user.tab();
    await user.tab();
    expect(quickActionButtons[0]).toHaveFocus();

    await user.tab();
    expect(quickActionButtons[1]).toHaveFocus();

    await user.tab();
    expect(quickActionButtons[2]).toHaveFocus();

    await user.tab();
    expect(quickActionButtons[3]).toHaveFocus();
  });
});
