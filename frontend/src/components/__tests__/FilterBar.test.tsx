import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import FilterBar from '../FilterBar';
import type { FilterBarState } from '../FilterBar';
import { createDefaultFilterState } from '../../lib/dashboardFilters';

describe('FilterBar', () => {
  it('renders the filter section with accessible label', () => {
    render(<FilterBar />);
    expect(screen.getByRole('region', { name: 'Dashboard filters' })).toBeInTheDocument();
  });

  it('renders date range preset buttons', () => {
    render(<FilterBar />);
    expect(screen.getByRole('button', { name: 'Today' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '7D' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '30D' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'MTD' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Custom' })).toBeInTheDocument();
  });

  it('marks the active date range preset as pressed', () => {
    const state: FilterBarState = {
      ...createDefaultFilterState(),
      dateRange: '30d',
    };
    render(<FilterBar state={state} />);
    expect(screen.getByRole('button', { name: '30D' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: '7D' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('calls onChange when a date preset is clicked', () => {
    const onChange = vi.fn();
    render(<FilterBar onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', { name: 'Today' }));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange.mock.calls[0][0].dateRange).toBe('today');
  });

  it('renders campaign search input', () => {
    render(<FilterBar />);
    expect(screen.getByPlaceholderText('Search campaigns')).toBeInTheDocument();
  });

  it('calls onChange when campaign search text changes', () => {
    const onChange = vi.fn();
    render(<FilterBar onChange={onChange} />);
    fireEvent.change(screen.getByPlaceholderText('Search campaigns'), {
      target: { value: 'brand' },
    });
    expect(onChange).toHaveBeenCalled();
    expect(onChange.mock.calls[0][0].campaignQuery).toBe('brand');
  });

  it('renders the channel multi-select button', () => {
    render(<FilterBar />);
    expect(screen.getByText('Channel')).toBeInTheDocument();
    expect(screen.getByText('All channels')).toBeInTheDocument();
  });

  it('renders account select when availableAccounts are provided', () => {
    const accounts = [
      { value: 'acc-1', label: 'Client A' },
      { value: 'acc-2', label: 'Client B' },
    ];
    render(<FilterBar availableAccounts={accounts} />);
    expect(screen.getByLabelText('Client')).toBeInTheDocument();
  });

  it('does not render account select when no accounts are provided', () => {
    render(<FilterBar />);
    expect(screen.queryByLabelText('Client')).not.toBeInTheDocument();
  });

  it('renders clear all button', () => {
    render(<FilterBar />);
    expect(screen.getByRole('button', { name: 'Clear all' })).toBeInTheDocument();
  });

  it('disables clear all button when filters are at defaults', () => {
    render(<FilterBar />);
    expect(screen.getByRole('button', { name: 'Clear all' })).toBeDisabled();
  });

  it('renders extended date range select', () => {
    render(<FilterBar />);
    expect(screen.getByLabelText('Longer window')).toBeInTheDocument();
  });
});
