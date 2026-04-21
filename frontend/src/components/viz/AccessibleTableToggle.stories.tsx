import type { Meta, StoryObj } from '@storybook/react';

import AccessibleTableToggle from './AccessibleTableToggle';

const meta: Meta<typeof AccessibleTableToggle> = {
  title: 'Viz/AccessibleTableToggle',
  component: AccessibleTableToggle,
  parameters: {
    layout: 'padded',
    a11y: { config: { rules: [{ id: 'color-contrast', enabled: true }] } },
    chromatic: { viewports: [375, 1280] },
  },
  tags: ['autodocs'],
};
export default meta;

type Story = StoryObj<typeof AccessibleTableToggle>;

const chartNode = (
  <div
    role="img"
    aria-label="Demo chart"
    style={{
      width: '100%',
      height: 220,
      background: 'var(--viz-series-0)',
      opacity: 0.25,
      borderRadius: 12,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: 'var(--color-text-primary)',
    }}
  >
    Chart view
  </div>
);

const tableNode = (
  <table>
    <caption>Demo table</caption>
    <thead>
      <tr>
        <th scope="col">Day</th>
        <th scope="col">Spend</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <th scope="row">Mon</th>
        <td>$120</td>
      </tr>
      <tr>
        <th scope="row">Tue</th>
        <td>$160</td>
      </tr>
    </tbody>
  </table>
);

export const Default: Story = {
  args: {
    chart: chartNode,
    table: tableNode,
    defaultView: 'chart',
    chartAriaLabel: 'Demo chart region',
  },
};

export const DefaultTable: Story = {
  args: {
    chart: chartNode,
    table: tableNode,
    defaultView: 'table',
    chartAriaLabel: 'Demo chart region',
  },
};

export const WithKeyboardFocus: Story = {
  args: {
    chart: chartNode,
    table: tableNode,
    defaultView: 'chart',
    chartAriaLabel: 'Demo chart region',
  },
  parameters: {
    docs: {
      description: {
        story:
          'Tab to the toggle button; press Enter or Space to flip between chart and table views. The inactive node is `hidden` + `aria-hidden` so focus only travels through the active view.',
      },
    },
  },
};
