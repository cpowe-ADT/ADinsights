import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it } from 'vitest';

import ToastContainer from '../ToastContainer';
import { useToastStore } from '../../stores/useToastStore';

describe('ToastContainer', () => {
  afterEach(() => {
    // Reset the store between tests
    act(() => {
      const { toasts, removeToast } = useToastStore.getState();
      toasts.forEach((t) => removeToast(t.id));
    });
  });

  it('renders toasts when added to the store', () => {
    render(<ToastContainer />);

    expect(screen.queryByRole('status')).toBeNull();

    act(() => {
      useToastStore.getState().addToast('Operation succeeded');
    });

    expect(screen.getByRole('status')).toHaveTextContent('Operation succeeded');
  });

  it('renders multiple toasts', () => {
    render(<ToastContainer />);

    act(() => {
      useToastStore.getState().addToast('First toast');
      useToastStore.getState().addToast('Second toast', 'error');
    });

    const statuses = screen.getAllByRole('status');
    expect(statuses).toHaveLength(2);
    expect(statuses[0]).toHaveTextContent('First toast');
    expect(statuses[1]).toHaveTextContent('Second toast');
  });

  it('dismiss button removes a toast', async () => {
    const user = userEvent.setup();
    render(<ToastContainer />);

    act(() => {
      useToastStore.getState().addToast('Dismissible toast');
    });

    expect(screen.getByRole('status')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Dismiss notification' }));

    expect(screen.queryByRole('status')).toBeNull();
  });

  it('applies the correct data-variant attribute', () => {
    render(<ToastContainer />);

    act(() => {
      useToastStore.getState().addToast('Error toast', 'error');
    });

    expect(screen.getByRole('status')).toHaveAttribute('data-variant', 'error');
  });
});
