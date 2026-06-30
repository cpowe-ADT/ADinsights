import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'jest-axe';
import { describe, expect, it } from 'vitest';

import AccessibleTableToggle from './AccessibleTableToggle';

const renderToggle = (defaultView: 'chart' | 'table' = 'chart') =>
  render(
    <AccessibleTableToggle
      defaultView={defaultView}
      chart={<div data-testid="chart-node">chart</div>}
      table={<div data-testid="table-node">table</div>}
      chartAriaLabel="Demo chart"
    />,
  );

describe('AccessibleTableToggle', () => {
  it('renders both chart and table nodes; inactive is hidden', () => {
    renderToggle('chart');
    const chartNode = screen.getByTestId('chart-node');
    const tableNode = screen.getByTestId('table-node');
    expect(chartNode).toBeInTheDocument();
    expect(tableNode).toBeInTheDocument();
    expect(tableNode.parentElement).toHaveAttribute('aria-hidden', 'true');
    expect(tableNode.parentElement).toHaveAttribute('hidden');
  });

  it('starts with aria-pressed=false when chart view is default', () => {
    renderToggle('chart');
    const btn = screen.getByRole('button');
    expect(btn).toHaveAttribute('aria-pressed', 'false');
    expect(btn).toHaveAttribute('aria-label', 'Show data table');
  });

  it('toggles to table view and flips aria-pressed via click', async () => {
    renderToggle('chart');
    const btn = screen.getByRole('button');
    await userEvent.click(btn);
    expect(btn).toHaveAttribute('aria-pressed', 'true');
    expect(btn).toHaveAttribute('aria-label', 'Show chart');
    // Table parent no longer hidden, chart parent is.
    expect(screen.getByTestId('table-node').parentElement).not.toHaveAttribute('hidden');
    expect(screen.getByTestId('chart-node').parentElement).toHaveAttribute('hidden');
  });

  it('toggles via Enter key', async () => {
    renderToggle('chart');
    const btn = screen.getByRole('button');
    btn.focus();
    await userEvent.keyboard('{Enter}');
    expect(btn).toHaveAttribute('aria-pressed', 'true');
  });

  it('toggles via Space key', async () => {
    renderToggle('chart');
    const btn = screen.getByRole('button');
    btn.focus();
    await userEvent.keyboard(' ');
    expect(btn).toHaveAttribute('aria-pressed', 'true');
  });

  it('starts with table when defaultView=table', () => {
    renderToggle('table');
    const btn = screen.getByRole('button');
    expect(btn).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('chart-node').parentElement).toHaveAttribute('hidden');
    expect(screen.getByTestId('table-node').parentElement).not.toHaveAttribute('hidden');
  });

  it('has no a11y violations', async () => {
    const { container } = renderToggle('chart');
    expect(await axe(container)).toHaveNoViolations();
  });
});
