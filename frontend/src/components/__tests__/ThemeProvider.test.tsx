import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ThemeProvider, useTheme } from '../ThemeProvider';

type MatchMediaController = {
  setMatches: (matches: boolean) => void;
};

function mockMatchMedia(initialMatches: boolean): MatchMediaController {
  let matches = initialMatches;
  const listeners = new Set<(event: MediaQueryListEvent) => void>();

  const matchMedia = vi.fn().mockImplementation((query: string) => ({
    media: query,
    matches,
    onchange: null,
    addEventListener: (_type: string, listener: (event: MediaQueryListEvent) => void) => {
      listeners.add(listener);
    },
    removeEventListener: (_type: string, listener: (event: MediaQueryListEvent) => void) => {
      listeners.delete(listener);
    },
    dispatchEvent: vi.fn(),
  }));

  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: matchMedia,
  });

  return {
    setMatches: (nextMatches: boolean) => {
      matches = nextMatches;
      const event = { matches: nextMatches } as MediaQueryListEvent;
      listeners.forEach((listener) => listener(event));
    },
  };
}

const ThemeProbe = () => {
  const { theme, toggleTheme } = useTheme();
  return (
    <div>
      <span data-testid="theme-value">{theme}</span>
      <button type="button" onClick={toggleTheme}>
        Toggle
      </button>
    </div>
  );
};

describe('ThemeProvider', () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.classList.remove('theme-light', 'theme-dark');
    document.documentElement.removeAttribute('data-theme');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('migrates legacy theme storage to the canonical key and syncs DOM markers', () => {
    mockMatchMedia(false);
    window.localStorage.setItem('adinsights:theme', 'dark');

    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>,
    );

    expect(screen.getByTestId('theme-value')).toHaveTextContent('dark');
    expect(document.documentElement.classList.contains('theme-dark')).toBe(true);
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(window.localStorage.getItem('adinsights-theme')).toBe('dark');
    expect(window.localStorage.getItem('adinsights:theme')).toBeNull();
  });

  it('follows system preference until a manual override is set', () => {
    const media = mockMatchMedia(false);

    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>,
    );

    expect(screen.getByTestId('theme-value')).toHaveTextContent('light');

    act(() => {
      media.setMatches(true);
    });
    expect(screen.getByTestId('theme-value')).toHaveTextContent('dark');

    fireEvent.click(screen.getByRole('button', { name: 'Toggle' }));
    expect(screen.getByTestId('theme-value')).toHaveTextContent('light');
    expect(window.localStorage.getItem('adinsights-theme')).toBe('light');

    act(() => {
      media.setMatches(true);
    });
    expect(screen.getByTestId('theme-value')).toHaveTextContent('light');
  });
});
