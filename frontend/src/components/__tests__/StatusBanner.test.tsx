import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import StatusBanner from '../StatusBanner';

describe('StatusBanner', () => {
  it('renders the message text', () => {
    render(<StatusBanner message="Sync in progress" />);
    expect(screen.getByText('Sync in progress')).toBeInTheDocument();
  });

  it('defaults to info tone with role="status"', () => {
    render(<StatusBanner message="Info message" />);
    const banner = screen.getByRole('status');
    expect(banner).toHaveAttribute('aria-live', 'polite');
    expect(banner).toHaveClass('status-banner--info');
  });

  it('renders warning tone', () => {
    render(<StatusBanner message="Warning" tone="warning" />);
    const banner = screen.getByRole('status');
    expect(banner).toHaveClass('status-banner--warning');
  });

  it('renders error tone with role="alert" and assertive aria-live', () => {
    render(<StatusBanner message="Error occurred" tone="error" />);
    const banner = screen.getByRole('alert');
    expect(banner).toHaveAttribute('aria-live', 'assertive');
    expect(banner).toHaveClass('status-banner--error');
  });

  it('renders ReactNode message content', () => {
    render(
      <StatusBanner message={<span data-testid="rich">Rich message</span>} />,
    );
    expect(screen.getByTestId('rich')).toBeInTheDocument();
  });

  it('renders an icon when provided', () => {
    render(
      <StatusBanner message="With icon" icon={<span data-testid="banner-icon">!</span>} />,
    );
    expect(screen.getByTestId('banner-icon')).toBeInTheDocument();
  });

  it('does not render icon container when icon is not provided', () => {
    const { container } = render(<StatusBanner message="No icon" />);
    expect(container.querySelector('.status-banner__icon')).not.toBeInTheDocument();
  });

  it('applies custom className', () => {
    const { container } = render(<StatusBanner message="Test" className="my-banner" />);
    expect(container.firstChild).toHaveClass('status-banner');
    expect(container.firstChild).toHaveClass('my-banner');
  });

  it('applies ariaLabel when provided', () => {
    render(<StatusBanner message="Test" ariaLabel="Custom label" />);
    const banner = screen.getByRole('status');
    expect(banner).toHaveAttribute('aria-label', 'Custom label');
  });

  it('applies title attribute when provided', () => {
    render(<StatusBanner message="Test" title="Tooltip text" />);
    const banner = screen.getByRole('status');
    expect(banner).toHaveAttribute('title', 'Tooltip text');
  });
});
