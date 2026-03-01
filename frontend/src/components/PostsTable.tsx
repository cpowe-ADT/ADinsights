import { useMemo, useState } from 'react';
import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  type SortingState,
  useReactTable,
} from '@tanstack/react-table';

import type { MetaPostListItem, MetricAvailabilityEntry } from '../lib/metaPageInsights';
import { formatNumber } from '../lib/format';
import MetricAvailabilityBadge from './MetricAvailabilityBadge';

type PostsTableProps = {
  rows: MetaPostListItem[];
  metricKey: string;
  availability?: MetricAvailabilityEntry;
  onOpenPost: (postId: string) => void;
};

const PostsTable = ({ rows, metricKey, availability, onOpenPost }: PostsTableProps) => {
  const [sorting, setSorting] = useState<SortingState>([{ id: 'created_time', desc: true }]);

  const columns = useMemo<Array<ColumnDef<MetaPostListItem>>>(
    () => [
      {
        accessorKey: 'post_id',
        header: 'Post ID',
      },
      {
        accessorKey: 'created_time',
        header: 'Created',
        cell: (context) => {
          const value = context.getValue<string | null>();
          return value ? value.slice(0, 10) : '—';
        },
      },
      {
        accessorKey: 'media_type',
        header: 'Media',
        cell: (context) => context.getValue<string>() || '—',
      },
      {
        accessorKey: 'message_snippet',
        header: 'Message',
        cell: (context) => context.getValue<string>() || '—',
      },
      {
        accessorKey: 'permalink',
        header: 'Facebook',
        enableSorting: false,
        cell: (context) => {
          const href = context.getValue<string>();
          if (!href) {
            return '—';
          }
          return (
            <a href={href} target="_blank" rel="noreferrer">
              Open
            </a>
          );
        },
      },
      {
        id: 'metric_value',
        header: () => (
          <div className="meta-post-metric-header">
            <span>{metricKey}</span>
            <MetricAvailabilityBadge metric={metricKey} availability={availability} />
          </div>
        ),
        accessorFn: (row) => row.metrics[metricKey],
        cell: (context) => {
          const raw = context.getValue<number | null>();
          return raw == null ? '—' : formatNumber(raw);
        },
      },
      {
        id: 'actions',
        header: '',
        enableSorting: false,
        cell: (context) => (
          <button className="button tertiary" type="button" onClick={() => onOpenPost(context.row.original.post_id)}>
            Open
          </button>
        ),
      },
    ],
    [availability, metricKey, onOpenPost],
  );

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <article className="panel">
      <div className="meta-posts-toolbar">
        <h3>Posts</h3>
      </div>
      <div className="table-responsive">
        <table className="dashboard-table">
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id} className="dashboard-table__header-row">
                {headerGroup.headers.map((header) => (
                  <th key={header.id} className="dashboard-table__header-cell">
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id} className="dashboard-table__row dashboard-table__row--zebra">
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="dashboard-table__cell">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </article>
  );
};

export default PostsTable;
