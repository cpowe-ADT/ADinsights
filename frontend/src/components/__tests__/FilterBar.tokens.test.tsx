import { render } from '@testing-library/react';
import { axe } from 'jest-axe';
import { useLayoutEffect } from 'react';
import { readFileSync } from 'node:fs';
import path from 'node:path';

import FilterBar from '../FilterBar';
import { ThemeProvider, useTheme } from '../ThemeProvider';

type ThemeName = 'light' | 'dark';

type TokenMap = Record<string, string>;

const appStylesSource = readFileSync(path.resolve(process.cwd(), 'src/styles.css'), 'utf8');

const themeStylesSource = readFileSync(path.resolve(process.cwd(), 'src/styles/theme.css'), 'utf8');

const themeTokenExpectations: Record<ThemeName, TokenMap> = {
  light: {
    '--shell-filterbar-surface': 'rgba(248, 250, 252, 0.95)',
    '--shell-filterbar-border': 'rgba(15, 23, 42, 0.08)',
    '--shell-filterchip-surface': 'var(--color-slate-200)',
    '--shell-filterchip-text': 'var(--color-slate-700)',
    '--shell-filterchip-active': 'var(--color-blue-600)',
    '--shell-filterchip-text-active': 'var(--color-white)',
    '--header-title-text': 'var(--color-text-inverse)',
    '--auth-heading-text': 'var(--color-text-primary)',
    '--surface-elevated-text': 'var(--color-text-primary)',
    '--home-card-surface': 'rgba(255, 255, 255, 0.92)',
    '--home-section-title': 'var(--color-slate-900)',
    '--home-cta-secondary-text': 'var(--header-title-text)',
  },
  dark: {
    '--shell-filterbar-surface': 'rgba(15, 23, 42, 0.9)',
    '--shell-filterbar-border': 'rgba(148, 163, 184, 0.2)',
    '--shell-filterchip-surface': 'rgba(148, 163, 184, 0.18)',
    '--shell-filterchip-text': 'rgba(226, 232, 240, 0.9)',
    '--shell-filterchip-active': 'var(--color-blue-500)',
    '--shell-filterchip-text-active': 'var(--color-slate-950)',
    '--header-title-text': '#f8fafc',
    '--auth-heading-text': '#f1f5f9',
    '--surface-elevated-text': '#e2e8f0',
    '--home-card-surface': 'rgba(15, 23, 42, 0.84)',
    '--home-section-title': '#f8fafc',
    '--home-cta-secondary-text': 'rgba(241, 245, 249, 0.95)',
  },
};

const renderFilterBar = (theme: ThemeName) => {
  const Harness = ({ activeTheme }: { activeTheme: ThemeName }) => {
    const { setTheme } = useTheme();

    useLayoutEffect(() => {
      setTheme(activeTheme);
    }, [setTheme, activeTheme]);

    return <FilterBar />;
  };

  return render(
    <ThemeProvider>
      <Harness activeTheme={theme} />
    </ThemeProvider>,
  );
};

const expectAppStylesUseTokens = () => {
  expect(appStylesSource).toMatch(/\.filter-bar[\s\S]*background:\s*var\(--shell-filterbar-surface\)/);
  expect(appStylesSource).toMatch(/\.filter-bar[\s\S]*border-bottom:\s*1px\s+solid\s+var\(--shell-filterbar-border\)/);
  expect(appStylesSource).toMatch(/\.filter-chip[\s\S]*background:\s*var\(--shell-filterchip-surface\)/);
  expect(appStylesSource).toMatch(/\.filter-chip[\s\S]*color:\s*var\(--shell-filterchip-text\)/);
  expect(appStylesSource).toMatch(/\.filter-chip--active[\s\S]*background:\s*var\(--shell-filterchip-active\)/);
  expect(appStylesSource).toMatch(/\.filter-chip--active[\s\S]*color:\s*var\(--shell-filterchip-text-active\)/);
};

const expectThemeStylesDeclareTokens = (theme: ThemeName) => {
  const tokens = themeTokenExpectations[theme];
  Object.entries(tokens).forEach(([token, value]) => {
    expect(themeStylesSource).toContain(`${token}: ${value}`);
  });
};

describe('FilterBar tokens', () => {
  it('references shell tokens in stylesheets and remains accessible', async () => {
    expectAppStylesUseTokens();
    expectThemeStylesDeclareTokens('light');

    const { container } = renderFilterBar('light');
    expect(document.documentElement.classList.contains('theme-light')).toBe(true);
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');

    const results = await axe(container, {
      rules: {
        'aria-input-field-name': { enabled: false },
        'aria-required-children': { enabled: false },
      },
    });
    expect(results).toHaveNoViolations();
  });

  it('switches theme classes and exposes dark token definitions', () => {
    renderFilterBar('dark');
    expect(document.documentElement.classList.contains('theme-dark')).toBe(true);
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expectThemeStylesDeclareTokens('dark');
  });
});
