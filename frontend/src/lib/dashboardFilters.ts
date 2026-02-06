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

export const DEFAULT_CHANNELS = ['Meta Ads', 'Google Ads', 'LinkedIn', 'TikTok'];

const CHANNEL_ALIASES: Record<string, string> = {
  'Meta Ads': 'meta',
  Meta: 'meta',
  'Google Ads': 'google_ads',
  Google: 'google_ads',
  LinkedIn: 'linkedin',
  TikTok: 'tiktok',
};

const CHANNEL_LABELS: Record<string, string> = {
  meta: 'Meta Ads',
  google_ads: 'Google Ads',
  linkedin: 'LinkedIn',
  tiktok: 'TikTok',
};

const DATE_RANGE_PRESETS = new Set<DateRangePreset>(['today', '7d', '30d', 'mtd', 'custom']);

const FILTER_QUERY_KEYS = {
  dateRange: 'date_range',
  startDate: 'start_date',
  endDate: 'end_date',
  channels: 'channels',
  campaignSearch: 'campaign_search',
};

const toInputDate = (date: Date): string => {
  const iso = new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString();
  return iso.slice(0, 10);
};

export const createDefaultCustomRange = (): FilterBarState['customRange'] => {
  const today = new Date();
  const startOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
  return {
    start: toInputDate(startOfMonth),
    end: toInputDate(today),
  };
};

export const createDefaultFilterState = (): FilterBarState => ({
  dateRange: '7d',
  customRange: createDefaultCustomRange(),
  channels: [],
  campaignQuery: '',
});

const normalizeDateValue = (value: string | undefined, fallback: string): string => {
  if (typeof value !== 'string') {
    return fallback;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed : fallback;
};

const normalizeDateRange = (start: string, end: string): { start: string; end: string } => {
  if (start > end) {
    return { start: end, end: start };
  }
  return { start, end };
};

export const normalizeChannelValue = (value: string): string => {
  const trimmed = value.trim();
  if (!trimmed) {
    return '';
  }
  if (CHANNEL_ALIASES[trimmed]) {
    return CHANNEL_ALIASES[trimmed];
  }
  return trimmed
    .toLowerCase()
    .replace(/&/g, 'and')
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');
};

export const resolveFilterRange = (filters: FilterBarState): { start: string; end: string } => {
  const today = new Date();
  const end = toInputDate(today);
  let start = end;

  switch (filters.dateRange) {
    case 'today': {
      start = end;
      break;
    }
    case '7d': {
      const startDate = new Date(today);
      startDate.setDate(startDate.getDate() - 6);
      start = toInputDate(startDate);
      break;
    }
    case '30d': {
      const startDate = new Date(today);
      startDate.setDate(startDate.getDate() - 29);
      start = toInputDate(startDate);
      break;
    }
    case 'mtd': {
      const startDate = new Date(today.getFullYear(), today.getMonth(), 1);
      start = toInputDate(startDate);
      break;
    }
    case 'custom': {
      const fallback = createDefaultCustomRange();
      const normalizedStart = normalizeDateValue(filters.customRange.start, fallback.start);
      const normalizedEnd = normalizeDateValue(filters.customRange.end, fallback.end);
      return normalizeDateRange(normalizedStart, normalizedEnd);
    }
    default: {
      break;
    }
  }

  return normalizeDateRange(start, end);
};

export const buildFilterQueryParams = (filters: FilterBarState): Record<string, string> => {
  const { start, end } = resolveFilterRange(filters);
  const params: Record<string, string> = {
    [FILTER_QUERY_KEYS.startDate]: start,
    [FILTER_QUERY_KEYS.endDate]: end,
  };

  const channelValues = filters.channels
    .map(normalizeChannelValue)
    .filter(Boolean);
  if (channelValues.length > 0) {
    params[FILTER_QUERY_KEYS.channels] = Array.from(new Set(channelValues)).join(',');
  }

  const query = filters.campaignQuery.trim();
  if (query) {
    params[FILTER_QUERY_KEYS.campaignSearch] = query;
  }

  return params;
};

export const buildFilterUrlParams = (filters: FilterBarState): Record<string, string> => {
  const params = buildFilterQueryParams(filters);
  params[FILTER_QUERY_KEYS.dateRange] = filters.dateRange;
  return params;
};

export const serializeFilterQueryParams = (filters: FilterBarState): string => {
  const params = buildFilterUrlParams(filters);
  const entries = Object.entries(params).filter(([, value]) => value);
  entries.sort(([a], [b]) => a.localeCompare(b));
  return new URLSearchParams(entries).toString();
};

export const parseFilterQueryParams = (
  searchParams: URLSearchParams,
  fallback: FilterBarState = createDefaultFilterState(),
): FilterBarState => {
  const dateRangeParam = searchParams.get(FILTER_QUERY_KEYS.dateRange) ?? undefined;
  const dateRange = DATE_RANGE_PRESETS.has(dateRangeParam as DateRangePreset)
    ? (dateRangeParam as DateRangePreset)
    : fallback.dateRange;

  const startParam = searchParams.get(FILTER_QUERY_KEYS.startDate) ?? undefined;
  const endParam = searchParams.get(FILTER_QUERY_KEYS.endDate) ?? undefined;

  const { start: resolvedStart, end: resolvedEnd } = normalizeDateRange(
    normalizeDateValue(startParam, fallback.customRange.start),
    normalizeDateValue(endParam, fallback.customRange.end),
  );

  const channelParam = searchParams.get(FILTER_QUERY_KEYS.channels);
  const channels = channelParam
    ? channelParam
        .split(',')
        .map((value) => value.trim())
        .filter(Boolean)
        .map((value) => CHANNEL_LABELS[value] ?? value)
    : fallback.channels;

  const campaignQuery =
    searchParams.get(FILTER_QUERY_KEYS.campaignSearch)?.trim() ?? fallback.campaignQuery;

  const resolvedDateRange =
    dateRangeParam && DATE_RANGE_PRESETS.has(dateRangeParam as DateRangePreset)
      ? (dateRangeParam as DateRangePreset)
      : startParam || endParam
      ? 'custom'
      : fallback.dateRange;

  return {
    dateRange: resolvedDateRange,
    customRange: {
      start: resolvedStart,
      end: resolvedEnd,
    },
    channels,
    campaignQuery,
  };
};

export const areFiltersEqual = (left: FilterBarState, right: FilterBarState): boolean => {
  if (left.dateRange !== right.dateRange) {
    return false;
  }

  const leftQuery = left.campaignQuery.trim();
  const rightQuery = right.campaignQuery.trim();
  if (leftQuery !== rightQuery) {
    return false;
  }

  const leftChannels = [...left.channels].sort();
  const rightChannels = [...right.channels].sort();
  if (leftChannels.length !== rightChannels.length) {
    return false;
  }
  for (let index = 0; index < leftChannels.length; index += 1) {
    if (leftChannels[index] !== rightChannels[index]) {
      return false;
    }
  }

  if (left.dateRange === 'custom') {
    const leftStart = left.customRange.start.trim();
    const leftEnd = left.customRange.end.trim();
    const rightStart = right.customRange.start.trim();
    const rightEnd = right.customRange.end.trim();
    if (leftStart !== rightStart || leftEnd !== rightEnd) {
      return false;
    }
  }

  return true;
};
