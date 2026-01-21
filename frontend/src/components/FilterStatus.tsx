import { useMemo } from 'react';

import {
  areFiltersEqual,
  createDefaultFilterState,
  type FilterBarState,
} from '../lib/dashboardFilters';
import useDashboardStore from '../state/useDashboardStore';

interface FilterStatusProps {
  className?: string;
}

const DATE_LABELS: Record<FilterBarState['dateRange'], string> = {
  today: 'Today',
  '7d': 'Last 7 days',
  '30d': 'Last 30 days',
  mtd: 'Month to date',
  custom: 'Custom range',
};

const formatFilterSummary = (filters: FilterBarState): string => {
  const parts: string[] = [];
  const dateLabel = DATE_LABELS[filters.dateRange] ?? 'Custom range';
  parts.push(`Date: ${dateLabel}`);

  if (filters.dateRange === 'custom') {
    parts.push(`Range: ${filters.customRange.start} -> ${filters.customRange.end}`);
  }

  if (filters.channels.length > 0) {
    parts.push(`Channels: ${filters.channels.join(', ')}`);
  }

  const query = filters.campaignQuery.trim();
  if (query) {
    parts.push(`Campaign: "${query}"`);
  }

  return parts.join(' · ');
};

const FilterStatus = ({ className }: FilterStatusProps) => {
  const filters = useDashboardStore((state) => state.filters);
  const isDefault = useMemo(
    () => areFiltersEqual(filters, createDefaultFilterState()),
    [filters],
  );

  if (isDefault) {
    return null;
  }

  const summary = formatFilterSummary(filters);
  const classes = ['filter-status', className].filter(Boolean).join(' ');

  return (
    <span className={classes} title={summary} aria-label={`Filters active. ${summary}`}>
      Filters active
    </span>
  );
};

export default FilterStatus;
