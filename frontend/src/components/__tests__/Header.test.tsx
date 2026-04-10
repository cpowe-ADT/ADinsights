import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import Header from '../Header';
import { ThemeProvider } from '../ThemeProvider';

const defaultProps = {
  title: 'Dashboard',
  navLinks: [
    { label: 'Overview', to: '/overview', end: true },
    { label: 'Reports', to: '/reports' },
  ],
  onLogout: vi.fn(),
};

const renderHeader = (props = {}) =>
  render(
    <MemoryRouter>
      <ThemeProvider>
        <Header {...defaultProps} {...props} />
      </ThemeProvider>
    </MemoryRouter>,
  );

describe('Header', () => {
  it('renders the application name', () => {
    renderHeader();
    expect(screen.getByText('ADinsights')).toBeInTheDocument();
  });

  it('renders the page title', () => {
    renderHeader({ title: 'Campaign Analysis' });
    expect(screen.getByText('Campaign Analysis')).toBeInTheDocument();
  });

  it('renders subtitle when provided', () => {
    renderHeader({ subtitle: 'Q1 2026' });
    expect(screen.getByText('Q1 2026')).toBeInTheDocument();
  });

  it('does not render subtitle when not provided', () => {
    const { container } = renderHeader();
    // subtitle div should not exist
    expect(container.querySelector('[class*="subtitle"]')).not.toBeInTheDocument();
  });

  it('renders navigation links', () => {
    renderHeader();
    expect(screen.getByRole('link', { name: 'Overview' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Reports' })).toBeInTheDocument();
  });

  it('renders primary navigation with correct aria label', () => {
    renderHeader();
    expect(screen.getByRole('navigation', { name: 'Primary' })).toBeInTheDocument();
  });

  it('renders home link with aria label', () => {
    renderHeader();
    expect(screen.getByRole('link', { name: 'ADinsights home' })).toBeInTheDocument();
  });

  it('renders the search form', () => {
    renderHeader();
    expect(screen.getByRole('search')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Search campaigns/)).toBeInTheDocument();
  });

  it('calls onSearch when search form is submitted', () => {
    const onSearch = vi.fn();
    renderHeader({ onSearch });
    const input = screen.getByPlaceholderText(/Search campaigns/);
    fireEvent.change(input, { target: { value: 'brand awareness' } });
    fireEvent.submit(input.closest('form')!);
    expect(onSearch).toHaveBeenCalledWith('brand awareness');
  });

  it('renders user email in the user menu button', () => {
    renderHeader({ userEmail: 'test@agency.com' });
    expect(screen.getByText('test@agency.com')).toBeInTheDocument();
  });

  it('renders "Account" when userEmail is not provided', () => {
    renderHeader({ userEmail: undefined });
    // The user button label and the menu identity both show "Account"
    expect(screen.getAllByText('Account').length).toBeGreaterThanOrEqual(1);
  });

  it('opens user menu on click and shows sign out button', () => {
    renderHeader({ userEmail: 'test@agency.com' });
    const userButton = screen.getByRole('button', { name: /test@agency.com/ });
    fireEvent.click(userButton);
    expect(screen.getByRole('menuitem', { name: 'Sign out' })).toBeInTheDocument();
  });

  it('calls onLogout when sign out is clicked', () => {
    const onLogout = vi.fn();
    renderHeader({ userEmail: 'test@agency.com', onLogout });
    fireEvent.click(screen.getByRole('button', { name: /test@agency.com/ }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Sign out' }));
    expect(onLogout).toHaveBeenCalledTimes(1);
  });

  it('renders theme toggle button', () => {
    renderHeader();
    const toggle = screen.getByRole('button', { name: /Switch to (dark|light) mode/ });
    expect(toggle).toBeInTheDocument();
  });

  it('renders metric picker when metricOptions are provided', () => {
    const metricOptions = [
      { label: 'Spend', value: 'spend' },
      { label: 'Impressions', value: 'impressions' },
    ];
    const onMetricChange = vi.fn();
    renderHeader({
      metricOptions,
      selectedMetric: 'spend',
      onMetricChange,
    });
    expect(screen.getByText('Map metric')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Spend')).toBeInTheDocument();
  });

  it('does not render metric picker when metricOptions are not provided', () => {
    renderHeader();
    expect(screen.queryByText('Map metric')).not.toBeInTheDocument();
  });
});
