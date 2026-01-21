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
    start_date: start,
    end_date: end,
  };

  const channelValues = filters.channels
    .map(normalizeChannelValue)
    .filter(Boolean);
  if (channelValues.length > 0) {
    params.channels = Array.from(new Set(channelValues)).join(',');
  }

  const query = filters.campaignQuery.trim();
  if (query) {
    params.campaign = query;
  }

  return params;
};

export const serializeFilterQueryParams = (filters: FilterBarState): string => {
  const params = buildFilterQueryParams(filters);
  const entries = Object.entries(params).filter(([, value]) => value);
  entries.sort(([a], [b]) => a.localeCompare(b));
  return new URLSearchParams(entries).toString();
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
