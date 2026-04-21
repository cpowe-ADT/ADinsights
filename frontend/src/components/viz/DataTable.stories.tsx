import type { Meta, StoryObj } from '@storybook/react';
import type { ColumnDef } from '@tanstack/react-table';

import VizDataTable from './DataTable';

interface CampaignRow {
  id: string;
  campaign: string;
  platform: string;
  status: string;
  spend: number;
  conversions: number;
}

const columns: ColumnDef<CampaignRow>[] = [
  { accessorKey: 'campaign', header: 'Campaign' },
  { accessorKey: 'platform', header: 'Platform' },
  { accessorKey: 'status', header: 'Status' },
  {
    accessorKey: 'spend',
    header: 'Spend',
    cell: ({ getValue }) => `$${Number(getValue()).toLocaleString()}`,
    meta: { isNumeric: true },
  },
  {
    accessorKey: 'conversions',
    header: 'Conversions',
    meta: { isNumeric: true },
  },
];

const baseRows: CampaignRow[] = [
  { id: 'r1', campaign: 'Awareness Boost', platform: 'Meta', status: 'Active', spend: 2400, conversions: 64 },
  { id: 'r2', campaign: 'Conversion Surge', platform: 'Google', status: 'Paused', spend: 1850, conversions: 52 },
  { id: 'r3', campaign: 'Remarketing Push', platform: 'Meta', status: 'Active', spend: 1320, conversions: 41 },
  { id: 'r4', campaign: 'Retention Nurture', platform: 'Google', status: 'Active', spend: 640, conversions: 18 },
];

const longRows: CampaignRow[] = Array.from({ length: 24 }).map((_, i) => ({
  id: `c${i}`,
  campaign: `Campaign ${i + 1}`,
  platform: i % 2 === 0 ? 'Meta' : 'Google',
  status: i % 3 === 0 ? 'Paused' : 'Active',
  spend: 500 + i * 83,
  conversions: 10 + i * 3,
}));

const meta: Meta<typeof VizDataTable<CampaignRow>> = {
  title: 'Viz/DataTable',
  component: VizDataTable,
  parameters: {
    layout: 'padded',
    a11y: { config: { rules: [{ id: 'color-contrast', enabled: true }] } },
    chromatic: { viewports: [375, 1280] },
  },
  tags: ['autodocs'],
};

export default meta;

type Story = StoryObj<typeof VizDataTable<CampaignRow>>;

export const Default: Story = {
  args: {
    columns,
    data: baseRows,
    caption: 'Campaign performance',
  },
};

export const Loading: Story = {
  args: {
    columns,
    data: [],
    caption: 'Campaign performance',
    emptyMessage: 'Loading…',
  },
};

export const Empty: Story = {
  args: {
    columns,
    data: [],
    caption: 'Campaign performance',
    emptyMessage: 'No campaigns for the selected filters.',
  },
};

export const WithCsvExport: Story = {
  args: {
    columns,
    data: baseRows,
    caption: 'Campaign performance',
    csvFilename: 'campaigns.csv',
  },
};

export const RowClick: Story = {
  args: {
    columns,
    data: baseRows,
    caption: 'Clickable campaign rows',
  },
};

export const LongList: Story = {
  args: {
    columns,
    data: longRows,
    caption: '24 campaigns',
  },
};

export const DarkTheme: Story = {
  args: {
    columns,
    data: baseRows,
    caption: 'Campaign performance',
  },
  decorators: [
    (StoryComponent) => (
      <div
        data-theme="dark"
        style={{ background: 'var(--color-surface-card)', padding: 16 }}
      >
        <StoryComponent />
      </div>
    ),
  ],
};
