import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import DashboardState from '../DashboardState';

describe('DashboardState', () => {
  describe('loading variant', () => {
    it('renders a loading spinner with default message', () => {
      render(<DashboardState variant="loading" />);
      const status = screen.getByRole('status');
      expect(status).toHaveAttribute('aria-busy', 'true');
      expect(screen.getByText('Loading dashboard data...')).toBeInTheDocument();
    });

    it('renders a custom loading message', () => {
      render(<DashboardState variant="loading" message="Fetching metrics..." />);
      expect(screen.getByText('Fetching metrics...')).toBeInTheDocument();
    });
  });

  describe('error variant', () => {
    it('renders default error title and message', () => {
      render(<DashboardState variant="error" />);
      expect(screen.getByText('Unable to load data')).toBeInTheDocument();
      expect(screen.getByText('Please try again in a moment.')).toBeInTheDocument();
    });

    it('renders custom title and message', () => {
      render(
        <DashboardState variant="error" title="Network error" message="Check your connection." />,
      );
      expect(screen.getByText('Network error')).toBeInTheDocument();
      expect(screen.getByText('Check your connection.')).toBeInTheDocument();
    });

    it('renders an action button with default label', () => {
      const onAction = vi.fn();
      render(<DashboardState variant="error" onAction={onAction} />);
      const button = screen.getByRole('button', { name: 'Retry load' });
      expect(button).toBeInTheDocument();
    });

    it('calls onAction when the retry button is clicked', () => {
      const onAction = vi.fn();
      render(<DashboardState variant="error" onAction={onAction} />);
      fireEvent.click(screen.getByRole('button', { name: 'Retry load' }));
      expect(onAction).toHaveBeenCalledTimes(1);
    });

    it('renders a custom action label', () => {
      render(
        <DashboardState variant="error" actionLabel="Reload now" onAction={() => {}} />,
      );
      expect(screen.getByRole('button', { name: 'Reload now' })).toBeInTheDocument();
    });
  });

  describe('empty variant', () => {
    it('renders default empty title and message', () => {
      render(<DashboardState variant="empty" />);
      expect(screen.getByText('No data yet')).toBeInTheDocument();
      expect(screen.getByText('Data will appear once your next sync finishes.')).toBeInTheDocument();
    });

    it('renders action button when onAction is provided', () => {
      const onAction = vi.fn();
      render(<DashboardState variant="empty" onAction={onAction} />);
      const button = screen.getByRole('button', { name: 'Refresh data' });
      expect(button).toBeInTheDocument();
      fireEvent.click(button);
      expect(onAction).toHaveBeenCalledTimes(1);
    });

    it('does not render action button when onAction is not provided', () => {
      render(<DashboardState variant="empty" />);
      expect(screen.queryByRole('button')).not.toBeInTheDocument();
    });
  });

  describe('no-results variant', () => {
    it('renders default no-results title and message', () => {
      render(<DashboardState variant="no-results" />);
      expect(screen.getByText('No results found')).toBeInTheDocument();
      expect(screen.getByText('Try adjusting filters to widen the view.')).toBeInTheDocument();
    });

    it('renders clear filters action when onAction is provided', () => {
      const onAction = vi.fn();
      render(<DashboardState variant="no-results" onAction={onAction} />);
      expect(screen.getByRole('button', { name: 'Clear filters' })).toBeInTheDocument();
    });
  });

  describe('layout prop', () => {
    it('applies panel layout class by default', () => {
      const { container } = render(<DashboardState variant="empty" />);
      expect(container.firstChild).toHaveClass('dashboard-state--panel');
    });

    it('applies page layout class', () => {
      const { container } = render(<DashboardState variant="empty" layout="page" />);
      expect(container.firstChild).toHaveClass('dashboard-state--page');
    });

    it('applies compact layout class', () => {
      const { container } = render(<DashboardState variant="empty" layout="compact" />);
      expect(container.firstChild).toHaveClass('dashboard-state--compact');
    });
  });

  describe('className prop', () => {
    it('appends custom className', () => {
      const { container } = render(<DashboardState variant="empty" className="my-custom" />);
      expect(container.firstChild).toHaveClass('my-custom');
      expect(container.firstChild).toHaveClass('dashboard-state');
    });
  });
});
