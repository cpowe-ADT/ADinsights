import '@testing-library/jest-dom/vitest';
import { createElement } from 'react';
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

const styleTag = document.createElement('style');
styleTag.innerHTML = `${globalStyles}\n${themeStyles}\n${appStyles}`;
document.head.appendChild(styleTag);
