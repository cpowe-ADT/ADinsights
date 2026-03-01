export const META_PAGE_DATE_PRESETS = ['last_7d', 'last_28d', 'last_90d', 'custom'] as const;

export type MetaPageDatePreset = (typeof META_PAGE_DATE_PRESETS)[number];

type MetaPageDateInput = {
  datePreset: string;
  since?: string;
  until?: string;
};

type MetaPageDateParams = {
  date_preset: string;
  since?: string;
  until?: string;
};

type MetaRangeOptions = {
  now?: Date;
  timeZone?: string;
  windowDays?: number;
};

function getDatePartsInTimeZone(date: Date, timeZone: string): { year: number; month: number; day: number } {
  const formatter = new Intl.DateTimeFormat('en-US', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
  const parts = formatter.formatToParts(date);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return {
    year: Number(values.year),
    month: Number(values.month),
    day: Number(values.day),
  };
}

function shiftIsoDateByDays(isoDate: string, days: number): string {
  const [year, month, day] = isoDate.split('-').map((value) => Number(value));
  const utcDate = new Date(Date.UTC(year, month - 1, day, 12));
  utcDate.setUTCDate(utcDate.getUTCDate() + days);
  const nextYear = utcDate.getUTCFullYear();
  const nextMonth = String(utcDate.getUTCMonth() + 1).padStart(2, '0');
  const nextDay = String(utcDate.getUTCDate()).padStart(2, '0');
  return `${nextYear}-${nextMonth}-${nextDay}`;
}

export function normalizeMetaPageDatePreset(value: string): MetaPageDatePreset {
  return META_PAGE_DATE_PRESETS.includes(value as MetaPageDatePreset)
    ? (value as MetaPageDatePreset)
    : 'last_28d';
}

export function toMetaPageDateParams(input: MetaPageDateInput): MetaPageDateParams {
  const payload: MetaPageDateParams = { date_preset: input.datePreset };
  if (input.datePreset === 'custom') {
    payload.since = input.since;
    payload.until = input.until;
  }
  return payload;
}

export function createMetaPageDefaultCustomRange({
  now = new Date(),
  timeZone = 'America/Jamaica',
  windowDays = 28,
}: MetaRangeOptions = {}): { since: string; until: string } {
  const { year, month, day } = getDatePartsInTimeZone(now, timeZone);
  const currentDate = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
  const until = shiftIsoDateByDays(currentDate, -1);
  const since = shiftIsoDateByDays(until, -(windowDays - 1));
  return { since, until };
}
