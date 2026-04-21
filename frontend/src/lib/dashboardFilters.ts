export type DateRangePreset =
  | 'today'
  | '7d'
  | '30d'
  | '60d'
  | '90d'
  | '180d'
  | '365d'
  | 'mtd'
  | 'custom';

export type FilterBarState = {
  dateRange: DateRangePreset;
  customRange: {
    start: string;
    end: string;
  };
  accountId: string;
  channels: string[];
  campaignQuery: string;
  /**
   * Sprint 8 of Client grouping: scopes the combined/single-platform dashboards
   * to the linked platform accounts of one Client. Empty string means
   * unscoped (legacy behaviour).
   */
  clientId: string;
  /**
   * Sprint 8 of Client grouping: toggleable platform list for the Combined
   * view. Empty array means "use backend-configured defaults" (parity with
   * legacy behaviour). Values are backend platform keys, e.g. 'meta_ads',
   * 'google_ads', 'meta_page'. Unknown keys are silently dropped by the
   * backend.
   */
  platforms: string[];
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

const DATE_RANGE_PRESETS = new Set<DateRangePreset>([
  'today',
  '7d',
  '30d',
  '60d',
  '90d',
  '180d',
  '365d',
  'mtd',
  'custom',
]);

const FILTER_QUERY_KEYS = {
  dateRange: 'date_range',
  startDate: 'start_date',
  endDate: 'end_date',
  accountId: 'account_id',
  channels: 'channels',
  campaignSearch: 'campaign_search',
  clientId: 'client_id',
  platforms: 'platforms',
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
  accountId: '',
  channels: [],
  campaignQuery: '',
  clientId: '',
  platforms: [],
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
  const resolveTrailingDays = (days: number): string => {
    const startDate = new Date(today);
    startDate.setDate(startDate.getDate() - (days - 1));
    return toInputDate(startDate);
  };

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
      start = resolveTrailingDays(30);
      break;
    }
    case '60d': {
      start = resolveTrailingDays(60);
      break;
    }
    case '90d': {
      start = resolveTrailingDays(90);
      break;
    }
    case '180d': {
      start = resolveTrailingDays(180);
      break;
    }
    case '365d': {
      start = resolveTrailingDays(365);
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

  const accountId = filters.accountId.trim();
  if (accountId) {
    params[FILTER_QUERY_KEYS.accountId] = accountId;
  }

  const channelValues = filters.channels.map(normalizeChannelValue).filter(Boolean);
  if (channelValues.length > 0) {
    params[FILTER_QUERY_KEYS.channels] = Array.from(new Set(channelValues)).join(',');
  }

  const query = filters.campaignQuery.trim();
  if (query) {
    params[FILTER_QUERY_KEYS.campaignSearch] = query;
  }

  const clientId = (filters.clientId ?? '').trim();
  if (clientId) {
    params[FILTER_QUERY_KEYS.clientId] = clientId;
  }

  const platforms = (filters.platforms ?? [])
    .map((value) => value.trim())
    .filter(Boolean);
  if (platforms.length > 0) {
    params[FILTER_QUERY_KEYS.platforms] = Array.from(new Set(platforms)).join(',');
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
  const startParam = searchParams.get(FILTER_QUERY_KEYS.startDate) ?? undefined;
  const endParam = searchParams.get(FILTER_QUERY_KEYS.endDate) ?? undefined;

  const { start: resolvedStart, end: resolvedEnd } = normalizeDateRange(
    normalizeDateValue(startParam, fallback.customRange.start),
    normalizeDateValue(endParam, fallback.customRange.end),
  );

  const accountId = searchParams.get(FILTER_QUERY_KEYS.accountId)?.trim() ?? fallback.accountId;
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

  const clientId =
    searchParams.get(FILTER_QUERY_KEYS.clientId)?.trim() ?? fallback.clientId;

  const platformsParam = searchParams.get(FILTER_QUERY_KEYS.platforms);
  const platforms = platformsParam
    ? platformsParam
        .split(',')
        .map((value) => value.trim())
        .filter(Boolean)
    : fallback.platforms;

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
    accountId,
    channels,
    campaignQuery,
    clientId,
    platforms,
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

  if (left.accountId.trim() !== right.accountId.trim()) {
    return false;
  }

  if ((left.clientId ?? '').trim() !== (right.clientId ?? '').trim()) {
    return false;
  }

  const leftPlatforms = [...(left.platforms ?? [])].sort();
  const rightPlatforms = [...(right.platforms ?? [])].sort();
  if (leftPlatforms.length !== rightPlatforms.length) {
    return false;
  }
  for (let index = 0; index < leftPlatforms.length; index += 1) {
    if (leftPlatforms[index] !== rightPlatforms[index]) {
      return false;
    }
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

// ── Route platform scope helpers ─────────────────────────────────────────────
// R6: Extracted from DashboardLayout.tsx so they can be unit-tested in isolation.

const META_ROUTE_PREFIX = '/dashboards/meta/';
const GOOGLE_ADS_ROUTE_PREFIX = '/dashboards/google-ads';

/**
 * Given a pathname, returns the platform scope that must be applied to
 * filters.platforms when on that route.  Returns null for combined routes
 * (no forced scope).
 */
export function resolveRoutePlatformScope(pathname: string): string[] | null {
  if (pathname.startsWith(META_ROUTE_PREFIX)) {
    return ['meta_ads'];
  }
  if (
    pathname === GOOGLE_ADS_ROUTE_PREFIX ||
    pathname.startsWith(`${GOOGLE_ADS_ROUTE_PREFIX}/`)
  ) {
    return ['google_ads'];
  }
  return null;
}

/**
 * Order-insensitive equality check for platform arrays.
 */
export function arePlatformArraysEqual(left: string[], right: string[]): boolean {
  if (left.length !== right.length) {
    return false;
  }
  const sortedLeft = [...left].sort();
  const sortedRight = [...right].sort();
  return sortedLeft.every((value, index) => value === sortedRight[index]);
}
