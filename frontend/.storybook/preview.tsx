import type { Preview } from '@storybook/react';
import { MemoryRouter } from 'react-router-dom';
import { useEffect, type ReactNode } from 'react';

import { ThemeProvider, useTheme } from '../src/components/ThemeProvider';
import { ToastProvider } from '../src/components/ToastProvider';

import '../src/styles/foundations.css';
import '../src/styles/theme.css';
import '../src/styles.css';
import '../src/styles/global.css';

type ThemeName = 'light' | 'dark';

const ThemeState = ({ theme, children }: { theme: ThemeName; children: ReactNode }) => {
  const { setTheme } = useTheme();

  useEffect(() => {
    setTheme(theme);
  }, [setTheme, theme]);

  return <>{children}</>;
};

const preview: Preview = {
  globalTypes: {
    theme: {
      name: 'Theme',
      description: 'Global theme for components',
      defaultValue: 'light',
      toolbar: {
        icon: 'circlehollow',
        items: [
          { value: 'light', title: 'Light', left: '🌞' },
          { value: 'dark', title: 'Dark', left: '🌙' },
        ],
      },
    },
  },
  decorators: [
    (Story, context) => {
      const entries = (context.parameters?.initialEntries as string[] | undefined) ?? ['/'];

      return (
        <MemoryRouter initialEntries={entries}>
          <ThemeProvider>
            <ThemeState theme={context.globals.theme as ThemeName}>
              <ToastProvider>
                <Story />
              </ToastProvider>
            </ThemeState>
          </ThemeProvider>
        </MemoryRouter>
      );
    },
  ],
  parameters: {
    actions: { argTypesRegex: '^on[A-Z].*' },
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
  },
};

export default preview;
