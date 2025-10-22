import type { Meta, StoryObj } from '@storybook/react';
import type { ColumnDef } from '@tanstack/react-table';

import DataTable from './DataTable';

interface SampleRow {
  id: string;
  campaign: string;
  platform: string;
  status: string;
  spend: number;
  conversions: number;
}

const columns: ColumnDef<SampleRow>[] = [
  {
    accessorKey: 'campaign',
    header: 'Campaign',
  },
  {
    accessorKey: 'platform',
    header: 'Platform',
  },
  {
    accessorKey: 'status',
    header: 'Status',
  },
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

const rows: SampleRow[] = [
  {
    id: 'row-1',
    campaign: 'Awareness Boost',
    platform: 'Meta',
    status: 'Active',
    spend: 2400,
    conversions: 64,
  },
  {
    id: 'row-2',
    campaign: 'Conversion Surge',
    platform: 'Google',
    status: 'Paused',
    spend: 1850,
    conversions: 52,
  },
  {
    id: 'row-3',
    campaign: 'Remarketing Push',
    platform: 'TikTok',
    status: 'Active',
    spend: 1320,
    conversions: 41,
  },
  {
    id: 'row-4',
    campaign: 'Retention Nurture',
    platform: 'Email',
    status: 'Draft',
    spend: 640,
    conversions: 18,
  },
];

interface TablePreviewProps {
  density?: 'comfortable' | 'compact';
}

const TablePreview = ({ density = 'comfortable' }: TablePreviewProps) => (
  <div style={{ padding: 'var(--space-4)' }}>
    <DataTable<SampleRow>
      columns={columns}
      data={rows}
      title="Campaign performance table"
      description="Baseline view for semantic table tokens."
      initialDensity={density}
    />
  </div>
);

const meta: Meta<typeof TablePreview> = {
  title: 'Components/DataTable',
  component: TablePreview,
  parameters: {
    chromatic: { viewports: [375, 1280] },
  },
};

export default meta;

type Story = StoryObj<typeof TablePreview>;

export const Comfortable: Story = {
  args: { density: 'comfortable' },
};

export const Compact: Story = {
  args: { density: 'compact' },
};
