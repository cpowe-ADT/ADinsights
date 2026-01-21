import { fileURLToPath } from 'node:url';

import type { StorybookConfig } from '@storybook/react-vite';
import { mergeConfig } from 'vite';

const childProcessShim = fileURLToPath(new URL('../src/shims/child_process.ts', import.meta.url));
const emptyShim = fileURLToPath(new URL('../src/shims/empty.ts', import.meta.url));

const config: StorybookConfig = {
  stories: ['../src/**/*.stories.@(ts|tsx|mdx)'],
  addons: ['@storybook/addon-essentials', '@storybook/addon-interactions'],
  framework: {
    name: '@storybook/react-vite',
    options: {},
  },
  docs: {
    autodocs: 'tag',
  },
  typescript: {
    reactDocgen: 'react-docgen-typescript',
  },
  staticDirs: ['../public'],
  viteFinal: async (config) =>
    mergeConfig(config, {
      resolve: {
        alias: {
          child_process: childProcessShim,
          fs: emptyShim,
          module: emptyShim,
        },
      },
      define: {
        'process.env': {},
        global: 'globalThis',
      },
    }),
};

export default config;
