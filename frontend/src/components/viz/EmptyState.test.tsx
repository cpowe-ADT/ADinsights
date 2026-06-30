import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'jest-axe';
import { describe, expect, it, vi } from 'vitest';

import EmptyState from '../EmptyState';
import VizEmptyIcon from './VizEmptyIcon';

describe('EmptyState (viz-kit presentation)', () => {
  it('renders title, message, and reason code', () => {
    const { container } = render(
      <EmptyState
        icon={<VizEmptyIcon />}
        title="No data to display"
        message="There is no data for the selected range."
        reasonCode="no_data_for_range"
      />,
    );
    expect(screen.getByText('No data to display')).toBeInTheDocument();
    expect(screen.getByText('There is no data for the selected range.')).toBeInTheDocument();
    expect(container.querySelector('[data-reason-code="no_data_for_range"]')).toBeInTheDocument();
  });

  it('omits the data-reason-code attribute when no reasonCode prop is set', () => {
    const { container } = render(
      <EmptyState icon={<VizEmptyIcon />} title="No data" message="Try something else." />,
    );
    const status = container.querySelector('.empty-state') as HTMLElement;
    expect(status).toBeInTheDocument();
    expect(status.getAttribute('data-reason-code')).toBeNull();
  });

  it('renders primary action and fires onAction when clicked', async () => {
    const handler = vi.fn();
    render(
      <EmptyState
        icon={<VizEmptyIcon />}
        title="Nothing here"
        message="Try retrying."
        actionLabel="Retry"
        onAction={handler}
      />,
    );
    await userEvent.click(screen.getByRole('button', { name: /retry/i }));
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('has no a11y violations', async () => {
    const { container } = render(
      <EmptyState
        icon={<VizEmptyIcon />}
        title="No data to display"
        message="There is no data for the selected range."
        reasonCode="no_data_for_range"
        actionLabel="Retry"
        onAction={() => {}}
      />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
