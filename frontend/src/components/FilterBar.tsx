import { useEffect, useId, useMemo, useRef, useState } from 'react';

export type DateRangePreset = 'today' | '7d' | '30d' | 'mtd' | 'custom';

export type FilterBarState = {
  dateRange: DateRangePreset;
  customRange: {
    start: string;
    end: string;
  };
  channels: string[];
  campaignQuery: string;
};

interface FilterBarProps {
  availableChannels?: string[];
  defaultState?: FilterBarState;
  onChange?: (nextState: FilterBarState) => void;
}

const toInputDate = (date: Date): string => {
  const iso = new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString();
  return iso.slice(0, 10);
};

const createDefaultCustomRange = () => {
  const today = new Date();
  const startOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
  return {
    start: toInputDate(startOfMonth),
    end: toInputDate(today),
  };
};

const createDefaultState = (): FilterBarState => ({
  dateRange: '7d',
  customRange: createDefaultCustomRange(),
  channels: [],
  campaignQuery: '',
});

const datePresets: { label: string; value: DateRangePreset }[] = [
  { label: 'Today', value: 'today' },
  { label: '7D', value: '7d' },
  { label: '30D', value: '30d' },
  { label: 'MTD', value: 'mtd' },
  { label: 'Custom', value: 'custom' },
];

const defaultChannels = ['Meta Ads', 'Google Ads', 'LinkedIn', 'TikTok'];

const FilterBar = ({ availableChannels, defaultState, onChange }: FilterBarProps) => {
  const resolvedDefaultState = useMemo(() => defaultState ?? createDefaultState(), [defaultState]);
  const [filters, setFilters] = useState<FilterBarState>(resolvedDefaultState);
  const [isCustomOpen, setIsCustomOpen] = useState(false);
  const [isChannelOpen, setIsChannelOpen] = useState(false);

  const customPopoverRef = useRef<HTMLDivElement | null>(null);
  const customButtonRef = useRef<HTMLButtonElement | null>(null);
  const channelPopoverRef = useRef<HTMLDivElement | null>(null);
  const channelButtonRef = useRef<HTMLButtonElement | null>(null);

  const customPopoverId = useId();
  const channelPopoverId = useId();

  useEffect(() => {
    onChange?.(filters);
  }, [filters, onChange]);

  useEffect(() => {
    setFilters({
      ...resolvedDefaultState,
      customRange: { ...resolvedDefaultState.customRange },
    });
  }, [resolvedDefaultState]);

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

  const channels = availableChannels ?? defaultChannels;

  const handleSelectPreset = (value: DateRangePreset) => {
    setFilters((prev) => ({
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
    setFilters((prev) => {
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
    setFilters((prev) => ({
      ...prev,
      dateRange: 'custom',
      customRange: {
        ...prev.customRange,
        [field]: value,
      },
    }));
  };

  const resetFilters = () => {
    setFilters({
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
                  <p className="filter-popover__hint">Calendar sync coming soon.</p>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>

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
            setFilters((prev) => ({
              ...prev,
              campaignQuery: event.target.value,
            }))
          }
        />
      </div>

      <button
        type="button"
        className="filter-chip filter-chip--clear"
        onClick={resetFilters}
        disabled={isDefaultState}
      >
        Clear all
      </button>
    </section>
  );
};

export default FilterBar;
