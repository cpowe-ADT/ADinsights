import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import SkeletonLoader from '../SkeletonLoader';

describe('SkeletonLoader', () => {
  it('renders 1 card skeleton by default', () => {
    const { container } = render(<SkeletonLoader variant="card" />);
    const cards = container.querySelectorAll('.skeleton--card');
    expect(cards).toHaveLength(1);
  });

  it('renders multiple card skeletons when count is provided', () => {
    const { container } = render(<SkeletonLoader variant="card" count={3} />);
    const cards = container.querySelectorAll('.skeleton--card');
    expect(cards).toHaveLength(3);
  });

  it('renders table variant with table-row classes', () => {
    const { container } = render(<SkeletonLoader variant="table" />);
    const rows = container.querySelectorAll('.skeleton--table-row');
    expect(rows.length).toBeGreaterThan(0);
  });

  it('renders multiple table skeletons when count > 1', () => {
    const { container } = render(<SkeletonLoader variant="table" count={2} />);
    const rows = container.querySelectorAll('.skeleton--table-row');
    // Each table skeleton has 5 rows, 2 tables = 10
    expect(rows).toHaveLength(10);
  });

  it('renders text variant with text-line classes', () => {
    const { container } = render(<SkeletonLoader variant="text" />);
    const lines = container.querySelectorAll('.skeleton--text-line');
    expect(lines.length).toBeGreaterThan(0);
  });

  it('renders stat variant with stat classes', () => {
    const { container } = render(<SkeletonLoader variant="stat" />);
    const statBox = container.querySelectorAll('.skeleton--stat-box');
    const statText = container.querySelectorAll('.skeleton--stat-text');
    expect(statBox).toHaveLength(1);
    expect(statText).toHaveLength(1);
  });

  it('renders multiple stat skeletons', () => {
    const { container } = render(<SkeletonLoader variant="stat" count={4} />);
    const statBoxes = container.querySelectorAll('.skeleton--stat-box');
    expect(statBoxes).toHaveLength(4);
  });

  it('applies skeleton-loader wrapper class', () => {
    const { container } = render(<SkeletonLoader variant="card" />);
    expect(container.querySelector('.skeleton-loader')).toBeTruthy();
  });

  it('has role="status" for accessibility', () => {
    const { container } = render(<SkeletonLoader variant="card" />);
    expect(container.querySelector('[role="status"]')).toBeTruthy();
  });
});
