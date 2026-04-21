import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'jest-axe';
import type { ColumnDef } from '@tanstack/react-table';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import VizDataTable from './DataTable';

interface Row {
  id: string;
  name: string;
  spend: number;
}

const columns: ColumnDef<Row>[] = [
  { accessorKey: 'name', header: 'Name' },
  { accessorKey: 'spend', header: 'Spend' },
];

const rows: Row[] = [
  { id: '1', name: 'Alpha', spend: 100 },
  { id: '2', name: 'Beta', spend: 250 },
];

describe('VizDataTable', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the caption', () => {
    render(<VizDataTable columns={columns} data={rows} caption="Campaign list" />);
    expect(screen.getByText('Campaign list')).toBeInTheDocument();
  });

  it('applies visually-hidden class when captionHidden is set', () => {
    const { container } = render(
      <VizDataTable
        columns={columns}
        data={rows}
        caption="Campaign list"
        captionHidden
      />,
    );
    const captionNode = container.querySelector('.viz-data-table__caption');
    expect(captionNode).toHaveClass('visually-hidden');
  });

  it('renders the Download CSV button only when csvFilename is set', () => {
    const { rerender } = render(
      <VizDataTable columns={columns} data={rows} caption="Campaigns" />,
    );
    expect(
      screen.queryByRole('button', { name: /download csv/i }),
    ).not.toBeInTheDocument();

    rerender(
      <VizDataTable
        columns={columns}
        data={rows}
        caption="Campaigns"
        csvFilename="campaigns.csv"
      />,
    );
    expect(
      screen.getByRole('button', { name: /download csv/i }),
    ).toBeInTheDocument();
  });

  it('creates a Blob URL when the CSV button is clicked', async () => {
    const createObjectURL = vi.fn(() => 'blob:mock');
    const revokeObjectURL = vi.fn();
    // JSDOM exposes URL but not these methods by default in all configurations.
    Object.defineProperty(window.URL, 'createObjectURL', {
      configurable: true,
      value: createObjectURL,
    });
    Object.defineProperty(window.URL, 'revokeObjectURL', {
      configurable: true,
      value: revokeObjectURL,
    });

    render(
      <VizDataTable
        columns={columns}
        data={rows}
        caption="Campaigns"
        csvFilename="campaigns.csv"
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: /download csv/i }));

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    const blob = createObjectURL.mock.calls[0][0] as Blob;
    // jsdom's Blob does not implement .text() — read via FileReader fallback.
    const text = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result ?? ''));
      reader.onerror = () => reject(reader.error);
      reader.readAsText(blob);
    });
    expect(text).toContain('Name,Spend');
    expect(text).toContain('Alpha,100');
    expect(text).toContain('Beta,250');
    expect(revokeObjectURL).toHaveBeenCalledTimes(1);
  });

  it('has no a11y violations', async () => {
    const { container } = render(
      <VizDataTable columns={columns} data={rows} caption="Campaigns" />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
