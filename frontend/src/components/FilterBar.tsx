import { useEffect, useId, useMemo, useRef, useState } from 'react';

import {
  DEFAULT_CHANNELS,
  areFiltersEqual,
  createDefaultFilterState,
  type DateRangePreset,
  type FilterBarState,
} from '../lib/dashboardFilters';

export type { DateRangePreset, FilterBarState } from '../lib/dashboardFilters';

export interface FilterBarAccountOption {
  value: string;
  label: string;
}

interface FilterBarProps {
  availableChannels?: string[];
  availableAccounts?: FilterBarAccountOption[];
  defaultState?: FilterBarState;
  state?: FilterBarState;
  onChange?: (nextState: FilterBarState) => void;
}

type FilterStateUpdater =
  | FilterBarState
  | ((previous: FilterBarState) => FilterBarState);

const datePresets: { label: string; value: DateRangePreset }[] = [
  { label: 'Today', value: 'today' },
  { label: '7D', value: '7d' },
  { label: '30D', value: '30d' },
  { label: 'MTD', value: 'mtd' },
  { label: 'Custom', value: 'custom' },
];

const extendedDatePresets: { label: string; value: DateRangePreset }[] = [
  { label: 'Last 60 days', value: '60d' },
  { label: 'Last 90 days', value: '90d' },
  { label: 'Last 180 days', value: '180d' },
  { label: 'Last 365 days', value: '365d' },
];

function cloneFilterState(filters: FilterBarState): FilterBarState {
  return {
    ...filters,
    channels: [...filters.channels],
    customRange: { ...filters.customRange },
  };
}

const FilterBar = ({
  availableChannels,
  availableAccounts,
  defaultState,
  state,
  onChange,
}: FilterBarProps) => {
  const resolvedDefaultState = useMemo(
    () => defaultState ?? createDefaultFilterState(),
    [defaultState],
  );
  const [internalFilters, setInternalFilters] = useState<FilterBarState>(() =>
    cloneFilterState(resolvedDefaultState),
  );
  const filters = state ?? internalFilters;
  const [isCustomOpen, setIsCustomOpen] = useState(false);
  const [isChannelOpen, setIsChannelOpen] = useState(false);

  const customPopoverRef = useRef<HTMLDivElement | null>(null);
  const customButtonRef = useRef<HTMLButtonElement | null>(null);
  const channelPopoverRef = useRef<HTMLDivElement | null>(null);
  const channelButtonRef = useRef<HTMLButtonElement | null>(null);

  const customPopoverId = useId();
  const channelPopoverId = useId();

  useEffect(() => {
    if (state) {
      return;
    }
    setInternalFilters((previous) => {
      if (areFiltersEqual(previous, resolvedDefaultState)) {
        return previous;
      }
      return cloneFilterState(resolvedDefaultState);
    });
  }, [resolvedDefaultState, state]);

  useEffect(() => {
    if (!isCustomOpen) {
      return;
    }

    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      if (
        customPopoverRef.current &&
        !customPopoverRef.current.contains(target) &&
        customButtonRef.current &&
        !customButtonRef.current.contains(target)
      ) {
        setIsCustomOpen(false);
      }
    };

    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsCustomOpen(false);
        customButtonRef.current?.focus();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKey);

    const firstInput =
      customPopoverRef.current?.querySelector<HTMLInputElement>("input[type='date']");
    firstInput?.focus();

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKey);
    };
  }, [isCustomOpen]);

  useEffect(() => {
    if (!isChannelOpen) {
      return;
    }

    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      if (
        channelPopoverRef.current &&
        !channelPopoverRef.current.contains(target) &&
        channelButtonRef.current &&
        !channelButtonRef.current.contains(target)
      ) {
        setIsChannelOpen(false);
      }
    };

    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsChannelOpen(false);
        channelButtonRef.current?.focus();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKey);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKey);
    };
  }, [isChannelOpen]);

  const channels = availableChannels ?? DEFAULT_CHANNELS;
  const selectedExtendedRange = extendedDatePresets.some((preset) => preset.value === filters.dateRange)
    ? filters.dateRange
    : '';

  const commitFilters = (updater: FilterStateUpdater) => {
    const next =
      typeof updater === 'function'
        ? (updater as (previous: FilterBarState) => FilterBarState)(filters)
        : updater;
    if (!state) {
      setInternalFilters(cloneFilterState(next));
    }
    onChange?.(next);
  };

  const handleSelectPreset = (value: DateRangePreset) => {
    commitFilters((prev) => ({
      ...prev,
      dateRange: value,
    }));
    if (value !== 'custom') {
      setIsCustomOpen(false);
    } else {
      setIsCustomOpen((current) => !current);
    }
  };

  const toggleChannel = (channel: string) => {
    commitFilters((prev) => {
      const exists = prev.channels.includes(channel);
      const nextChannels = exists
        ? prev.channels.filter((item) => item !== channel)
        : [...prev.channels, channel];
      return {
        ...prev,
        channels: nextChannels,
      };
    });
  };

  const updateCustomRange = (field: 'start' | 'end', value: string) => {
    commitFilters((prev) => ({
      ...prev,
      dateRange: 'custom',
      customRange: {
        ...prev.customRange,
        [field]: value,
      },
    }));
  };

  const resetFilters = () => {
    commitFilters({
      ...resolvedDefaultState,
      customRange: { ...resolvedDefaultState.customRange },
    });
    setIsCustomOpen(false);
    setIsChannelOpen(false);
  };

  const isDefaultState = useMemo(() => {
    const baseline = resolvedDefaultState;
    return (
      filters.dateRange === baseline.dateRange &&
      filters.accountId.trim() === baseline.accountId.trim() &&
      filters.campaignQuery.trim() === baseline.campaignQuery.trim() &&
      filters.channels.length === baseline.channels.length &&
      filters.channels.every((channel) => baseline.channels.includes(channel)) &&
      filters.customRange.start === baseline.customRange.start &&
      filters.customRange.end === baseline.customRange.end
    );
  }, [filters, resolvedDefaultState]);

  const selectedChannelLabel = useMemo(() => {
    if (filters.channels.length === 0) {
      return 'All channels';
    }

    if (filters.channels.length === 1) {
      return filters.channels[0];
    }

    return `${filters.channels.length} selected`;
  }, [filters.channels]);

  return (
    <section className="filter-bar" aria-label="Dashboard filters">
      <div className="filter-bar__row">
        <div className="filter-group" role="group" aria-label="Date range presets">
          {datePresets.map((preset) => {
            const isActive = filters.dateRange === preset.value;
            const isCustom = preset.value === 'custom';
            return (
              <div key={preset.value} className={isCustom ? 'filter-chip-wrapper' : undefined}>
                <button
                  type="button"
                  className={`filter-chip${isActive ? ' filter-chip--active' : ''}`}
                  aria-pressed={isActive}
                  aria-expanded={isCustom ? isCustomOpen : undefined}
                  aria-controls={isCustom ? customPopoverId : undefined}
                  onClick={() => handleSelectPreset(preset.value)}
                  ref={isCustom ? customButtonRef : undefined}
                >
                  {preset.label}
                </button>
                {isCustom ? (
                  <div
                    ref={customPopoverRef}
                    id={customPopoverId}
                    role="dialog"
                    aria-label="Custom date range"
                    className={`filter-popover${isCustomOpen ? ' filter-popover--open' : ''}`}
                  >
                    <div className="filter-popover__content">
                      <label className="filter-popover__field">
                        <span>Start</span>
                        <input
                          type="date"
                          value={filters.customRange.start}
                          onChange={(event) => updateCustomRange('start', event.target.value)}
                        />
                      </label>
                      <label className="filter-popover__field">
                        <span>End</span>
                        <input
                          type="date"
                          value={filters.customRange.end}
                          onChange={(event) => updateCustomRange('end', event.target.value)}
                        />
                      </label>
                    </div>
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>

        <div className="filter-field filter-search">
          <label htmlFor="extended-reporting-window">Longer window</label>
          <select
            id="extended-reporting-window"
            value={selectedExtendedRange}
            onChange={(event) => {
              const nextValue = event.target.value as DateRangePreset | '';
              if (!nextValue) {
                return;
              }
              commitFilters((prev) => ({
                ...prev,
                dateRange: nextValue,
              }));
              setIsCustomOpen(false);
            }}
          >
            <option value="">More ranges</option>
            {extendedDatePresets.map((preset) => (
              <option key={preset.value} value={preset.value}>
                {preset.label}
              </option>
            ))}
          </select>
        </div>

        {availableAccounts && availableAccounts.length > 0 ? (
          <div className="filter-field filter-search">
            <label htmlFor="client-account">Client</label>
            <select
              id="client-account"
              value={filters.accountId}
              onChange={(event) =>
                commitFilters((prev) => ({
                  ...prev,
                  accountId: event.target.value,
                }))
              }
            >
              <option value="">All clients</option>
              {availableAccounts.map((account) => (
                <option key={account.value} value={account.value}>
                  {account.label}
                </option>
              ))}
            </select>
          </div>
        ) : null}

        <div className="filter-field filter-multiselect" ref={channelPopoverRef}>
          <button
            type="button"
            ref={channelButtonRef}
            className="filter-multiselect__button"
            aria-haspopup="listbox"
            aria-expanded={isChannelOpen}
            aria-controls={channelPopoverId}
            onClick={() => setIsChannelOpen((open) => !open)}
          >
            <span className="filter-field__label">Channel</span>
            <span className="filter-field__value">{selectedChannelLabel}</span>
          </button>
          <div
            id={channelPopoverId}
            role="listbox"
            aria-multiselectable="true"
            className={`filter-popover filter-popover--menu${isChannelOpen ? ' filter-popover--open' : ''}`}
          >
            <ul>
              {channels.map((channel) => {
                const isSelected = filters.channels.includes(channel);
                return (
                  <li key={channel}>
                    <label className="filter-option">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleChannel(channel)}
                      />
                      <span>{channel}</span>
                    </label>
                  </li>
                );
              })}
            </ul>
          </div>
        </div>

        <div className="filter-field filter-search">
          <label htmlFor="campaign-search">Campaign</label>
          <input
            id="campaign-search"
            type="search"
            placeholder="Search campaigns"
            value={filters.campaignQuery}
            onChange={(event) =>
              commitFilters((prev) => ({
                ...prev,
                campaignQuery: event.target.value,
              }))
            }
          />
        </div>
      </div>

      <div className="filter-bar__actions">
        <button
          type="button"
          className="filter-chip filter-chip--clear"
          onClick={resetFilters}
          disabled={isDefaultState}
        >
          Clear all
        </button>
      </div>
    </section>
  );
};

export default FilterBar;
