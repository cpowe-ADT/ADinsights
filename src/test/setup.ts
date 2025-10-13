// Extend Vitest with jest-dom matchers
import '@testing-library/jest-dom/vitest';
import React from 'react';

// Polyfill ResizeObserver (jsdom doesn’t have it)
class ResizeObserver {
  private cb: ResizeObserverCallback;
  constructor(cb: ResizeObserverCallback) { this.cb = cb; }
  observe() {/* no-op */}
  unobserve() {/* no-op */}
  disconnect() {/* no-op */}
}
// @ts-ignore
global.ResizeObserver = ResizeObserver as any;

// Optional: matchMedia mock for libraries reading it
// @ts-ignore
global.matchMedia = global.matchMedia || function () {
  return {
    matches: false,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
    media: '',
    onchange: null,
  };
};

// Recharts & JSDOM: mock ResponsiveContainer so children get real size
import { vi } from 'vitest';
vi.mock('recharts', async (orig) => {
  const mod = await (orig() as Promise<typeof import('recharts')>);
  const MockResponsiveContainer = (props: any) => {
    const { width = '100%', height = 300, children } = props;
    // Recharts supports function-as-child or element; support both:
    const w = typeof width === 'number' ? width : 800;
    const h = typeof height === 'number' ? height : 300;
    return React.createElement(
      'div',
      { style: { width: `${w}px`, height: `${h}px` } },
      typeof children === 'function' ? children({ width: w, height: h }) : children
    );
  };
  return { ...mod, ResponsiveContainer: MockResponsiveContainer };
});
