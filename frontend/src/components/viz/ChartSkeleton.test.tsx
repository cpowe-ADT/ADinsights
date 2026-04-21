import { render } from '@testing-library/react';
import { axe } from 'jest-axe';
import { describe, expect, it } from 'vitest';

import ChartSkeleton from './ChartSkeleton';

describe('ChartSkeleton', () => {
  it('renders a line-variant root with given height', () => {
    const { container } = render(<ChartSkeleton variant="line" height={240} />);
    const root = container.querySelector('.viz-chart-skeleton') as HTMLElement;
    expect(root).toBeInTheDocument();
    expect(root).toHaveAttribute('role', 'presentation');
    expect(root).toHaveAttribute('aria-hidden', 'true');
    expect(root.style.height).toBe('240px');
  });

  it('renders a kpi-strip grid with four placeholders', () => {
    const { container } = render(<ChartSkeleton variant="kpi-strip" />);
    const root = container.querySelector('.viz-chart-skeleton') as HTMLElement;
    expect(root).toBeInTheDocument();
    expect(root.children.length).toBe(4);
  });

  it('renders the requested number of table rows', () => {
    const { container } = render(<ChartSkeleton variant="table" rows={5} />);
    // 1 header skeleton + 5 row skeletons = 6 Skeleton elements.
    const skeletons = container.querySelectorAll('.skeleton');
    expect(skeletons.length).toBeGreaterThanOrEqual(6);
  });

  it('has no a11y violations across all variants', async () => {
    const variants: Array<
      'line' | 'bar' | 'pie' | 'table' | 'kpi-strip' | 'kpi' | 'sparkline' | 'bubble'
    > = ['line', 'bar', 'pie', 'table', 'kpi-strip', 'kpi', 'sparkline', 'bubble'];
    for (const variant of variants) {
      const { container, unmount } = render(<ChartSkeleton variant={variant} />);
      expect(await axe(container)).toHaveNoViolations();
      unmount();
    }
  });
});
