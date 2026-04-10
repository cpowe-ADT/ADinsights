import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import EmptyState from '../EmptyState';

const defaultIcon = <span data-testid="icon">icon</span>;

describe('EmptyState', () => {
  it('renders title and message', () => {
    render(<EmptyState icon={defaultIcon} title="No data" message="Nothing to show." />);
    expect(screen.getByText('No data')).toBeInTheDocument();
    expect(screen.getByText('Nothing to show.')).toBeInTheDocument();
  });

  it('renders the icon', () => {
    render(<EmptyState icon={defaultIcon} title="No data" message="Nothing to show." />);
    expect(screen.getByTestId('icon')).toBeInTheDocument();
  });

  it('renders primary action button when actionLabel and onAction are provided', () => {
    const onAction = vi.fn();
    render(
      <EmptyState
        icon={defaultIcon}
        title="No data"
        message="Nothing here."
        actionLabel="Retry"
        onAction={onAction}
      />,
    );
    const button = screen.getByRole('button', { name: 'Retry' });
    expect(button).toBeInTheDocument();
    fireEvent.click(button);
    expect(onAction).toHaveBeenCalledTimes(1);
  });

  it('does not render action button when actionLabel is missing', () => {
    render(<EmptyState icon={defaultIcon} title="No data" message="Nothing." />);
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('does not render action button when onAction is missing', () => {
    render(
      <EmptyState icon={defaultIcon} title="No data" message="Nothing." actionLabel="Click" />,
    );
    expect(screen.queryByRole('button', { name: 'Click' })).not.toBeInTheDocument();
  });

  it('renders secondary action button when provided', () => {
    const onSecondary = vi.fn();
    render(
      <EmptyState
        icon={defaultIcon}
        title="No data"
        message="Nothing."
        secondaryActionLabel="Learn more"
        onSecondaryAction={onSecondary}
      />,
    );
    const button = screen.getByRole('button', { name: 'Learn more' });
    expect(button).toBeInTheDocument();
    fireEvent.click(button);
    expect(onSecondary).toHaveBeenCalledTimes(1);
  });

  it('applies custom className', () => {
    const { container } = render(
      <EmptyState icon={defaultIcon} title="T" message="M" className="extra" />,
    );
    expect(container.firstChild).toHaveClass('empty-state');
    expect(container.firstChild).toHaveClass('extra');
  });

  it('has role="status" and aria-live="polite"', () => {
    render(<EmptyState icon={defaultIcon} title="T" message="M" />);
    const status = screen.getByRole('status');
    expect(status).toHaveAttribute('aria-live', 'polite');
  });
});
