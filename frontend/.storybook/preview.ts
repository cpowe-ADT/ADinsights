import type { Preview } from '@storybook/react';

import '../src/styles/theme.css';
import '../src/styles.css';
import '../src/styles/global.css';
import '../src/styles/dashboard.css';

const preview: Preview = {
  parameters: {
    actions: { argTypesRegex: '^on[A-Z].*' },
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/,
      },
    },
  },
};

export default preview;
