import { render, screen } from '@testing-library/react';
import { axe } from 'jest-axe';
import { describe, expect, it } from 'vitest';

import Sparkline from './Sparkline';

const sample = [
  { date: 'd0', value: 10 },
  { date: 'd1', value: 14 },
  { date: 'd2', value: 12 },
  { date: 'd3', value: 18 },
];

describe('Sparkline', () => {
  it('renders with role="img" and aria-label', () => {
    render(<Sparkline data={sample} ariaLabel="Spend trend" />);
    expect(screen.getByRole('img', { name: /spend trend/i })).toBeInTheDocument();
  });

  it('renders a no-data image when data is empty', () => {
    render(<Sparkline data={[]} ariaLabel="Spend" />);
    expect(screen.getByRole('img', { name: /spend: no data/i })).toBeInTheDocument();
  });

  it('renders the skeleton when isLoading', () => {
    const { container } = render(<Sparkline data={sample} ariaLabel="Spend" isLoading />);
    expect(container.querySelector('.viz-chart-skeleton')).toBeInTheDocument();
  });

  it('has no a11y violations', async () => {
    const { container } = render(<Sparkline data={sample} ariaLabel="Spend trend" />);
    expect(await axe(container)).toHaveNoViolations();
  });

  it('has no a11y violations in empty state', async () => {
    const { container } = render(<Sparkline data={[]} ariaLabel="Spend" />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
