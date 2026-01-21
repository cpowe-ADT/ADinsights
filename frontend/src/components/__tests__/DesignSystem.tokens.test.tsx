import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const read = (relativePath: string) =>
  readFileSync(resolve(process.cwd(), relativePath), 'utf-8');

describe('design system guardrails', () => {
  it('documents the core sections', () => {
    const doc = read('DESIGN_SYSTEM.md');
    expect(doc).toContain('Principles');
    expect(doc).toContain('Typography');
    expect(doc).toContain('Components');
    expect(doc).toContain('Motion');
  });

  it('keeps critical tokens and component classes', () => {
    const theme = read('src/styles/theme.css');
    const styles = read('src/styles.css');

    expect(theme).toContain('--color-text-primary');
    expect(theme).toContain('--metric-card-surface');
    expect(styles).toContain('.metric-card');
    expect(styles).toContain('.chart-card__header');
    expect(styles).toContain('.data-table__header');
  });
});
