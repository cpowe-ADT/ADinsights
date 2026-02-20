import type {
  CampaignPerformanceResponse,
  CampaignPerformanceRow,
  CampaignTrendPoint,
  CreativePerformanceRow,
  BudgetPacingRow,
  ParishAggregate,
  TenantMetricsResolved,
} from '../state/useDashboardStore';
import { normalizeChannelValue, resolveFilterRange, type FilterBarState } from './dashboardFilters';

const STORAGE_KEY = 'adinsights-uploaded-dataset';

export type UploadedCampaignMetricRow = {
  date: string;
  campaignId: string;
  campaignName: string;
  platform: string;
  parish?: string;
  spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  revenue?: number;
  roas?: number;
  status?: string;
  objective?: string;
  startDate?: string;
  endDate?: string;
  currency?: string;
};

export type UploadedParishMetricRow = {
  date?: string;
  parish: string;
  spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  revenue?: number;
  roas?: number;
  campaignCount?: number;
  currency?: string;
};

export type UploadedBudgetRow = {
  month: string;
  campaignName: string;
  plannedBudget: number;
  spendToDate?: number;
  projectedSpend?: number;
  pacingPercent?: number;
  parishes?: string[];
  platform?: string;
};

export type UploadedDataset = {
  campaignMetrics: UploadedCampaignMetricRow[];
  parishMetrics: UploadedParishMetricRow[];
  budgets: UploadedBudgetRow[];
  uploadedAt: string;
};

type ParishFallbackRow = {
  parish: string;
  spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  revenue?: number;
  currency?: string;
  campaignId: string;
  campaignCount?: number;
};

export type UploadParseResult<T> = {
  rows: T[];
  errors: string[];
  warnings: string[];
  headers: string[];
};

type StoredUploadState = {
  dataset: UploadedDataset;
  active: boolean;
};

type CsvTable = {
  headers: string[];
  rows: string[][];
};

const REQUIRED_CAMPAIGN_COLUMNS = [
  'date',
  'campaign_id',
  'campaign_name',
  'platform',
  'spend',
  'impressions',
  'clicks',
  'conversions',
];

const REQUIRED_PARISH_COLUMNS = ['parish', 'spend', 'impressions', 'clicks', 'conversions'];

const REQUIRED_BUDGET_COLUMNS = ['month', 'campaign_name', 'planned_budget'];

const COLUMN_ALIASES: Record<string, string[]> = {
  date: ['date', 'day', 'date_day'],
  campaign_id: ['campaign_id', 'campaignid', 'campaign id', 'campaign'],
  campaign_name: ['campaign_name', 'campaignname', 'campaign name', 'name'],
  platform: ['platform', 'channel', 'source', 'source_platform'],
  parish: ['parish', 'parish_name'],
  spend: ['spend', 'cost'],
  impressions: ['impressions'],
  clicks: ['clicks'],
  conversions: ['conversions'],
  revenue: ['revenue', 'conversion_value', 'conversion value'],
  roas: ['roas'],
  status: ['status'],
  objective: ['objective'],
  start_date: ['start_date', 'start date'],
  end_date: ['end_date', 'end date'],
  currency: ['currency'],
  campaign_count: ['campaign_count', 'campaign count'],
  month: ['month', 'period', 'date'],
  planned_budget: ['planned_budget', 'monthly_budget', 'budget', 'planned'],
  spend_to_date: ['spend_to_date', 'spend to date'],
  projected_spend: ['projected_spend', 'projected spend', 'forecast_spend'],
  pacing_percent: ['pacing_percent', 'pacing', 'pacing percent'],
  parishes: ['parishes', 'parish_list', 'parish list'],
};

function normalizeHeader(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');
}

function parseCsvRow(line: string): string[] {
  const result: string[] = [];
  let current = '';
  let inQuotes = false;

  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    if (char === '"') {
      if (inQuotes && line[index + 1] === '"') {
        current += '"';
        index += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (char === ',' && !inQuotes) {
      result.push(current);
      current = '';
      continue;
    }
    current += char;
  }
  result.push(current);
  return result.map((value) => value.trim());
}

function parseCsv(text: string): CsvTable {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (lines.length === 0) {
    return { headers: [], rows: [] };
  }

  const headers = parseCsvRow(lines[0] ?? '').map((header) => header.trim());
  const rows = lines.slice(1).map(parseCsvRow);
  return { headers, rows };
}

function resolveColumn(headers: string[], columnKey: string): number {
  const normalizedHeaders = headers.map(normalizeHeader);
  const aliases = COLUMN_ALIASES[columnKey] ?? [columnKey];
  for (const alias of aliases) {
    const normalized = normalizeHeader(alias);
    const index = normalizedHeaders.indexOf(normalized);
    if (index >= 0) {
      return index;
    }
  }
  return -1;
}

function parseNumber(
  value: string,
  field: string,
  errors: string[],
  rowIndex: number,
): number | undefined {
  const trimmed = value.trim();
  if (!trimmed) {
    errors.push(`Row ${rowIndex}: ${field} is required.`);
    return undefined;
  }
  const parsed = Number(trimmed.replace(/,/g, ''));
  if (!Number.isFinite(parsed)) {
    errors.push(`Row ${rowIndex}: ${field} is invalid.`);
    return undefined;
  }
  return parsed;
}

function parseOptionalNumber(value: string): number | undefined {
  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }
  const parsed = Number(trimmed.replace(/,/g, ''));
  return Number.isFinite(parsed) ? parsed : undefined;
}

function normalizeDate(value: string): string | undefined {
  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) {
    return trimmed;
  }
  const parsed = new Date(trimmed);
  if (Number.isNaN(parsed.getTime())) {
    return undefined;
  }
  return parsed.toISOString().slice(0, 10);
}

function normalizeMonth(value: string): string | undefined {
  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }
  if (/^\d{4}-\d{2}$/.test(trimmed)) {
    return `${trimmed}-01`;
  }
  const date = normalizeDate(trimmed);
  if (!date) {
    return undefined;
  }
  return `${date.slice(0, 7)}-01`;
}

function endOfMonth(date: string): string {
  const parsed = new Date(`${date}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) {
    return date;
  }
  const end = new Date(Date.UTC(parsed.getUTCFullYear(), parsed.getUTCMonth() + 1, 0));
  return end.toISOString().slice(0, 10);
}

function buildErrorsFromMissing(headers: string[], required: string[], errors: string[]): void {
  required.forEach((column) => {
    if (resolveColumn(headers, column) === -1) {
      errors.push(`Missing required column: ${column}`);
    }
  });
}

function parseCsvOrError(text: string, errors: string[]): CsvTable {
  const table = parseCsv(text);
  if (table.headers.length === 0) {
    errors.push('CSV file is empty or missing headers.');
  }
  return table;
}

export function parseCampaignCsv(text: string): UploadParseResult<UploadedCampaignMetricRow> {
  const errors: string[] = [];
  const warnings: string[] = [];
  const table = parseCsvOrError(text, errors);
  buildErrorsFromMissing(table.headers, REQUIRED_CAMPAIGN_COLUMNS, errors);
  if (table.rows.length === 0) {
    errors.push('CSV file has no data rows.');
  }
  if (errors.length > 0) {
    return { rows: [], errors, warnings, headers: table.headers };
  }

  const rows: UploadedCampaignMetricRow[] = [];
  table.rows.forEach((cells, index) => {
    const rowIndex = index + 2;
    const dateValue = cells[resolveColumn(table.headers, 'date')] ?? '';
    const date = normalizeDate(dateValue);
    if (!date) {
      errors.push(`Row ${rowIndex}: date is invalid.`);
      return;
    }

    const campaignId = cells[resolveColumn(table.headers, 'campaign_id')]?.trim() ?? '';
    const campaignName = cells[resolveColumn(table.headers, 'campaign_name')]?.trim() ?? '';
    const platform = cells[resolveColumn(table.headers, 'platform')]?.trim() ?? 'Unknown';

    if (!campaignId || !campaignName) {
      errors.push(`Row ${rowIndex}: campaign_id and campaign_name are required.`);
      return;
    }

    const spend = parseNumber(
      cells[resolveColumn(table.headers, 'spend')] ?? '',
      'spend',
      errors,
      rowIndex,
    );
    const impressions = parseNumber(
      cells[resolveColumn(table.headers, 'impressions')] ?? '',
      'impressions',
      errors,
      rowIndex,
    );
    const clicks = parseNumber(
      cells[resolveColumn(table.headers, 'clicks')] ?? '',
      'clicks',
      errors,
      rowIndex,
    );
    const conversions = parseNumber(
      cells[resolveColumn(table.headers, 'conversions')] ?? '',
      'conversions',
      errors,
      rowIndex,
    );
    if (
      typeof spend === 'undefined' ||
      typeof impressions === 'undefined' ||
      typeof clicks === 'undefined' ||
      typeof conversions === 'undefined'
    ) {
      return;
    }

    const parish = cells[resolveColumn(table.headers, 'parish')]?.trim() || undefined;
    const revenue = parseOptionalNumber(cells[resolveColumn(table.headers, 'revenue')] ?? '');
    const roas = parseOptionalNumber(cells[resolveColumn(table.headers, 'roas')] ?? '');
    const status = cells[resolveColumn(table.headers, 'status')]?.trim() || undefined;
    const objective = cells[resolveColumn(table.headers, 'objective')]?.trim() || undefined;
    const startDate = normalizeDate(cells[resolveColumn(table.headers, 'start_date')] ?? '');
    const endDate = normalizeDate(cells[resolveColumn(table.headers, 'end_date')] ?? '');
    const currency = cells[resolveColumn(table.headers, 'currency')]?.trim() || undefined;

    if (!parish) {
      warnings.push(`Row ${rowIndex}: parish missing. Using "Unknown".`);
    }

    rows.push({
      date,
      campaignId,
      campaignName,
      platform,
      parish,
      spend,
      impressions,
      clicks,
      conversions,
      revenue,
      roas,
      status,
      objective,
      startDate: startDate ?? undefined,
      endDate: endDate ?? undefined,
      currency,
    });
  });

  return { rows, errors, warnings, headers: table.headers };
}

export function parseParishCsv(text: string): UploadParseResult<UploadedParishMetricRow> {
  const errors: string[] = [];
  const warnings: string[] = [];
  const table = parseCsvOrError(text, errors);
  buildErrorsFromMissing(table.headers, REQUIRED_PARISH_COLUMNS, errors);
  if (table.rows.length === 0) {
    errors.push('CSV file has no data rows.');
  }
  if (errors.length > 0) {
    return { rows: [], errors, warnings, headers: table.headers };
  }

  const rows: UploadedParishMetricRow[] = [];
  table.rows.forEach((cells, index) => {
    const rowIndex = index + 2;
    const parish = cells[resolveColumn(table.headers, 'parish')]?.trim() ?? '';
    if (!parish) {
      errors.push(`Row ${rowIndex}: parish is required.`);
      return;
    }

    const spend = parseNumber(
      cells[resolveColumn(table.headers, 'spend')] ?? '',
      'spend',
      errors,
      rowIndex,
    );
    const impressions = parseNumber(
      cells[resolveColumn(table.headers, 'impressions')] ?? '',
      'impressions',
      errors,
      rowIndex,
    );
    const clicks = parseNumber(
      cells[resolveColumn(table.headers, 'clicks')] ?? '',
      'clicks',
      errors,
      rowIndex,
    );
    const conversions = parseNumber(
      cells[resolveColumn(table.headers, 'conversions')] ?? '',
      'conversions',
      errors,
      rowIndex,
    );
    if (
      typeof spend === 'undefined' ||
      typeof impressions === 'undefined' ||
      typeof clicks === 'undefined' ||
      typeof conversions === 'undefined'
    ) {
      return;
    }

    const date = normalizeDate(cells[resolveColumn(table.headers, 'date')] ?? '');
    const revenue = parseOptionalNumber(cells[resolveColumn(table.headers, 'revenue')] ?? '');
    const roas = parseOptionalNumber(cells[resolveColumn(table.headers, 'roas')] ?? '');
    const campaignCount = parseOptionalNumber(
      cells[resolveColumn(table.headers, 'campaign_count')] ?? '',
    );
    const currency = cells[resolveColumn(table.headers, 'currency')]?.trim() || undefined;

    rows.push({
      date,
      parish,
      spend,
      impressions,
      clicks,
      conversions,
      revenue,
      roas,
      campaignCount,
      currency,
    });
  });

  return { rows, errors, warnings, headers: table.headers };
}

export function parseBudgetCsv(text: string): UploadParseResult<UploadedBudgetRow> {
  const errors: string[] = [];
  const warnings: string[] = [];
  const table = parseCsvOrError(text, errors);
  buildErrorsFromMissing(table.headers, REQUIRED_BUDGET_COLUMNS, errors);
  if (table.rows.length === 0) {
    errors.push('CSV file has no data rows.');
  }
  if (errors.length > 0) {
    return { rows: [], errors, warnings, headers: table.headers };
  }

  const rows: UploadedBudgetRow[] = [];
  table.rows.forEach((cells, index) => {
    const rowIndex = index + 2;
    const monthValue = cells[resolveColumn(table.headers, 'month')] ?? '';
    const month = normalizeMonth(monthValue);
    if (!month) {
      errors.push(`Row ${rowIndex}: month is invalid.`);
      return;
    }

    const campaignName = cells[resolveColumn(table.headers, 'campaign_name')]?.trim() ?? '';
    if (!campaignName) {
      errors.push(`Row ${rowIndex}: campaign_name is required.`);
      return;
    }

    const plannedBudget = parseNumber(
      cells[resolveColumn(table.headers, 'planned_budget')] ?? '',
      'planned_budget',
      errors,
      rowIndex,
    );
    if (typeof plannedBudget === 'undefined') {
      return;
    }

    const spendToDate = parseOptionalNumber(
      cells[resolveColumn(table.headers, 'spend_to_date')] ?? '',
    );
    const projectedSpend = parseOptionalNumber(
      cells[resolveColumn(table.headers, 'projected_spend')] ?? '',
    );
    const pacingPercent = parseOptionalNumber(
      cells[resolveColumn(table.headers, 'pacing_percent')] ?? '',
    );
    const parishesValue = cells[resolveColumn(table.headers, 'parishes')] ?? '';
    const parishes = parishesValue
      .split(',')
      .map((value) => value.trim())
      .filter(Boolean);
    const platform = cells[resolveColumn(table.headers, 'platform')]?.trim() || undefined;

    rows.push({
      month,
      campaignName,
      plannedBudget,
      spendToDate,
      projectedSpend,
      pacingPercent,
      parishes: parishes.length > 0 ? parishes : undefined,
      platform,
    });
  });

  return { rows, errors, warnings, headers: table.headers };
}

export function loadUploadState(): { dataset?: UploadedDataset; active: boolean } {
  if (typeof window === 'undefined') {
    return { dataset: undefined, active: false };
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return { dataset: undefined, active: false };
    }
    const parsed = JSON.parse(raw) as StoredUploadState;
    if (!parsed?.dataset) {
      return { dataset: undefined, active: false };
    }
    return {
      dataset: parsed.dataset,
      active: Boolean(parsed.active),
    };
  } catch {
    return { dataset: undefined, active: false };
  }
}

export function saveUploadState(dataset: UploadedDataset, active: boolean): void {
  if (typeof window === 'undefined') {
    return;
  }
  const payload: StoredUploadState = { dataset, active };
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

export function clearUploadState(): void {
  if (typeof window === 'undefined') {
    return;
  }
  window.localStorage.removeItem(STORAGE_KEY);
}

function computeRevenue(row: UploadedCampaignMetricRow): number | undefined {
  if (typeof row.revenue === 'number') {
    return row.revenue;
  }
  if (typeof row.roas === 'number') {
    return row.roas * row.spend;
  }
  return undefined;
}

function resolveCurrency(dataset: UploadedDataset): string {
  const fromCampaign = dataset.campaignMetrics.find((row) => row.currency)?.currency ?? '';
  const fromParish = dataset.parishMetrics.find((row) => row.currency)?.currency ?? '';
  const resolved = fromCampaign || fromParish || 'JMD';
  return resolved.trim().toUpperCase();
}

function withinRange(date: string, start: string, end: string): boolean {
  return date >= start && date <= end;
}

export function buildMetricsFromUpload(
  dataset: UploadedDataset,
  filters: FilterBarState,
  tenantId?: string,
): TenantMetricsResolved {
  const { start, end } = resolveFilterRange(filters);
  const channelFilters = filters.channels.map(normalizeChannelValue).filter(Boolean);
  const query = filters.campaignQuery.trim().toLowerCase();

  const filteredCampaignRows = dataset.campaignMetrics.filter((row) => {
    if (!withinRange(row.date, start, end)) {
      return false;
    }
    if (channelFilters.length > 0) {
      const platformKey = normalizeChannelValue(row.platform ?? '');
      if (!platformKey || !channelFilters.includes(platformKey)) {
        return false;
      }
    }
    if (!query) {
      return true;
    }
    return row.campaignName.toLowerCase().includes(query);
  });

  const revenueTotals = filteredCampaignRows.reduce((acc, row) => {
    const revenue = computeRevenue(row);
    return acc + (revenue ?? 0);
  }, 0);

  const summaryTotals = filteredCampaignRows.reduce(
    (acc, row) => {
      acc.spend += row.spend;
      acc.impressions += row.impressions;
      acc.clicks += row.clicks;
      acc.conversions += row.conversions;
      return acc;
    },
    { spend: 0, impressions: 0, clicks: 0, conversions: 0 },
  );

  const trendMap = new Map<string, CampaignTrendPoint>();
  filteredCampaignRows.forEach((row) => {
    const entry = trendMap.get(row.date) ?? {
      date: row.date,
      spend: 0,
      conversions: 0,
      clicks: 0,
      impressions: 0,
    };
    entry.spend += row.spend;
    entry.conversions += row.conversions;
    entry.clicks += row.clicks;
    entry.impressions += row.impressions;
    trendMap.set(row.date, entry);
  });

  const trend = Array.from(trendMap.values()).sort((a, b) => a.date.localeCompare(b.date));

  const campaignRowsMap = new Map<string, CampaignPerformanceRow>();
  const campaignRevenueMap = new Map<string, number>();
  filteredCampaignRows.forEach((row) => {
    const existing = campaignRowsMap.get(row.campaignId);
    const revenue = computeRevenue(row) ?? 0;
    if (!existing) {
      campaignRowsMap.set(row.campaignId, {
        id: row.campaignId,
        name: row.campaignName,
        platform: row.platform,
        status: row.status ?? 'Active',
        objective: row.objective,
        parish: row.parish ?? 'Unknown',
        spend: row.spend,
        impressions: row.impressions,
        clicks: row.clicks,
        conversions: row.conversions,
        roas: row.spend > 0 ? revenue / row.spend : (row.roas ?? 0),
        ctr: row.impressions > 0 ? row.clicks / row.impressions : 0,
        cpc: row.clicks > 0 ? row.spend / row.clicks : 0,
        cpm: row.impressions > 0 ? (row.spend / row.impressions) * 1000 : 0,
        startDate: row.startDate ?? row.date,
        endDate: row.endDate ?? row.date,
      });
      campaignRevenueMap.set(row.campaignId, revenue);
      return;
    }

    existing.spend += row.spend;
    existing.impressions += row.impressions;
    existing.clicks += row.clicks;
    existing.conversions += row.conversions;
    const nextRevenue = (campaignRevenueMap.get(row.campaignId) ?? 0) + revenue;
    campaignRevenueMap.set(row.campaignId, nextRevenue);
    existing.roas = existing.spend > 0 ? nextRevenue / existing.spend : existing.roas;
    existing.ctr = existing.impressions > 0 ? existing.clicks / existing.impressions : 0;
    existing.cpc = existing.clicks > 0 ? existing.spend / existing.clicks : 0;
    existing.cpm = existing.impressions > 0 ? (existing.spend / existing.impressions) * 1000 : 0;
    existing.startDate =
      existing.startDate && existing.startDate < row.date ? existing.startDate : row.date;
    existing.endDate =
      existing.endDate && existing.endDate > row.date ? existing.endDate : row.date;
  });

  const campaignRows = Array.from(campaignRowsMap.values());
  const currency = resolveCurrency(dataset);
  const campaign: CampaignPerformanceResponse = {
    summary: {
      currency,
      totalSpend: summaryTotals.spend,
      totalImpressions: summaryTotals.impressions,
      totalClicks: summaryTotals.clicks,
      totalConversions: summaryTotals.conversions,
      averageRoas: summaryTotals.spend > 0 ? revenueTotals / summaryTotals.spend : 0,
    },
    trend,
    rows: campaignRows,
  };

  const parishSource: Array<UploadedParishMetricRow | ParishFallbackRow> =
    dataset.parishMetrics.length > 0
      ? dataset.parishMetrics.filter((row) => (row.date ? withinRange(row.date, start, end) : true))
      : filteredCampaignRows.map((row) => ({
          parish: row.parish ?? 'Unknown',
          spend: row.spend,
          impressions: row.impressions,
          clicks: row.clicks,
          conversions: row.conversions,
          revenue: computeRevenue(row),
          currency: row.currency,
          campaignId: row.campaignId,
        }));

  const parishMap = new Map<string, ParishAggregate>();
  const parishCampaigns = new Map<string, Set<string>>();
  const parishRevenueMap = new Map<string, number>();
  parishSource.forEach((row) => {
    const entry = parishMap.get(row.parish) ?? {
      parish: row.parish,
      spend: 0,
      impressions: 0,
      clicks: 0,
      conversions: 0,
      roas: 0,
      campaignCount: 0,
      currency,
    };
    entry.spend += row.spend;
    entry.impressions += row.impressions;
    entry.clicks += row.clicks;
    entry.conversions += row.conversions;
    const nextRevenue = (parishRevenueMap.get(row.parish) ?? 0) + (row.revenue ?? 0);
    parishRevenueMap.set(row.parish, nextRevenue);
    entry.roas = entry.spend > 0 ? nextRevenue / entry.spend : (entry.roas ?? 0);
    if (typeof row.campaignCount === 'number') {
      entry.campaignCount = row.campaignCount;
    } else if ('campaignId' in row && typeof row.campaignId === 'string') {
      const set = parishCampaigns.get(row.parish) ?? new Set<string>();
      set.add(row.campaignId);
      parishCampaigns.set(row.parish, set);
      entry.campaignCount = set.size;
    }
    parishMap.set(row.parish, entry);
  });

  const parish = Array.from(parishMap.values());

  const budgetRows = dataset.budgets.reduce<BudgetPacingRow[]>((acc, row) => {
    const monthStart = row.month;
    const monthEnd = endOfMonth(monthStart);
    const inRange = withinRange(monthStart, start, end) || withinRange(monthEnd, start, end);
    if (!inRange) {
      return acc;
    }

    let spendToDate = row.spendToDate;
    if (typeof spendToDate !== 'number') {
      spendToDate = filteredCampaignRows
        .filter((metric) => metric.campaignName === row.campaignName)
        .filter((metric) => withinRange(metric.date, monthStart, monthEnd))
        .reduce((sum, metric) => sum + metric.spend, 0);
    }
    const projectedSpend =
      typeof row.projectedSpend === 'number' ? row.projectedSpend : spendToDate;
    const pacingPercent =
      typeof row.pacingPercent === 'number'
        ? row.pacingPercent
        : row.plannedBudget > 0
          ? spendToDate / row.plannedBudget
          : 0;

    acc.push({
      id: `${row.campaignName}-${row.month}`,
      campaignName: row.campaignName,
      parishes: row.parishes,
      monthlyBudget: row.plannedBudget,
      spendToDate: spendToDate ?? 0,
      projectedSpend: projectedSpend ?? 0,
      pacingPercent,
      startDate: monthStart,
      endDate: monthEnd,
    });
    return acc;
  }, []);

  return {
    campaign,
    creative: [] as CreativePerformanceRow[],
    budget: budgetRows,
    parish,
    tenantId,
    currency,
    snapshotGeneratedAt: dataset.uploadedAt,
  };
}
