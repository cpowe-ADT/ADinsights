import '@testing-library/jest-dom/vitest';
import { createElement } from 'react';
import { configure } from '@testing-library/react';
import { expect } from 'vitest';
import { vi } from 'vitest';
import { toHaveNoViolations } from 'jest-axe';
import globalStyles from './styles/global.css?raw';
import themeStyles from './styles/theme.css?raw';
import appStyles from './styles.css?raw';

const routerFuture = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const;

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');

  const MemoryRouter = (props: Record<string, unknown>) =>
    createElement(actual.MemoryRouter, {
      ...props,
      future: props.future ?? routerFuture,
    });

  return {
    ...actual,
    MemoryRouter,
  };
});

expect.extend(toHaveNoViolations);
configure({ asyncUtilTimeout: 10000 });

// JSDOM does not implement scrollIntoView; several components (e.g. DataSources)
// call it imperatively. Polyfill it globally so full-suite runs don't fail with
// "scrollIntoView is not a function" and cascade collection-time errors into
// unrelated test files.
if (!window.HTMLElement.prototype.scrollIntoView) {
  window.HTMLElement.prototype.scrollIntoView = vi.fn();
}

const styleTag = document.createElement('style');
styleTag.innerHTML = `${globalStyles}\n${themeStyles}\n${appStyles}`;
document.head.appendChild(styleTag);
