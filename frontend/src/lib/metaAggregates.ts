/**
 * Pure aggregation helpers for Meta Accounts + Meta Insights pages.
 *
 * Extracted per S2 architect §5.1 to keep the route components lean and to
 * provide a stable surface for unit tests. No React, no store access — all
 * inputs are plain records typed against `lib/meta.ts`.
 */

import type { MetaCampaign, MetaInsightRecord } from './meta';

export interface InsightsKpis {
  spend: number;
  impressions: number;
  reach: number;
  clicks: number;
  conversions: number;
  ctr: number;
  cpm: number;
  cpc: number;
}

const numeric = (value: unknown): number => {
  if (value === null || value === undefined) return 0;
  const n = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(n) ? n : 0;
};

/** Sum headline KPIs from a flat list of insight rows. */
export const sumInsights = (rows: MetaInsightRecord[]): InsightsKpis => {
  let spend = 0;
  let impressions = 0;
  let reach = 0;
  let clicks = 0;
  let conversions = 0;
  for (const row of rows) {
    spend += numeric(row.spend);
    impressions += numeric(row.impressions);
    reach += numeric(row.reach);
    clicks += numeric(row.clicks);
    conversions += numeric(row.conversions);
  }
  const ctr = impressions > 0 ? clicks / impressions : 0;
  const cpm = impressions > 0 ? (spend / impressions) * 1000 : 0;
  const cpc = clicks > 0 ? spend / clicks : 0;
  return { spend, impressions, reach, clicks, conversions, ctr, cpm, cpc };
};

export interface TrendDayPoint {
  date: string;
  [key: string]: string | number;
}

/**
 * Group `level='account'` rows by `(date, account_external_id)` and produce
 * Recharts-compatible rows keyed by `date` with one numeric column per
 * account. Accounts missing a data point for a given date get `0`.
 *
 * Series keys are sanitized to account_external_id strings; the caller is
 * responsible for mapping those to display names for `TrendLine` labels.
 */
export const groupSpendByDateAccount = (
  rows: MetaInsightRecord[],
): { points: TrendDayPoint[]; accountIds: string[] } => {
  const byDate = new Map<string, Map<string, number>>();
  const allAccounts = new Set<string>();

  for (const row of rows) {
    const accountId = row.account_external_id ?? '';
    if (!accountId) continue;
    allAccounts.add(accountId);
    const dateMap = byDate.get(row.date) ?? new Map<string, number>();
    dateMap.set(accountId, (dateMap.get(accountId) ?? 0) + numeric(row.spend));
    byDate.set(row.date, dateMap);
  }

  const accountIds = [...allAccounts];
  const points: TrendDayPoint[] = [...byDate.entries()]
    .map(([date, accountMap]): TrendDayPoint => {
      const point: TrendDayPoint = { date };
      for (const accountId of accountIds) {
        point[accountId] = accountMap.get(accountId) ?? 0;
      }
      return point;
    })
    .sort((a, b) => String(a.date).localeCompare(String(b.date)));

  return { points, accountIds };
};

/**
 * Compute the median spend-per-day across all accounts. Used as the
 * peer-avg series when a single account filter is active.
 */
export const computePeerMedian = (rows: MetaInsightRecord[]): { date: string; value: number }[] => {
  const byDate = new Map<string, Map<string, number>>();
  for (const row of rows) {
    const accountId = row.account_external_id ?? '';
    if (!accountId) continue;
    const m = byDate.get(row.date) ?? new Map<string, number>();
    m.set(accountId, (m.get(accountId) ?? 0) + numeric(row.spend));
    byDate.set(row.date, m);
  }
  const median = (values: number[]): number => {
    if (values.length === 0) return 0;
    const sorted = [...values].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 === 1 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
  };
  return [...byDate.entries()]
    .map(([date, accountMap]) => ({ date, value: median([...accountMap.values()]) }))
    .sort((a, b) => a.date.localeCompare(b.date));
};

/**
 * Return top-N account_external_ids by total spend across the window.
 */
export const topAccountsBySpend = (rows: MetaInsightRecord[], n: number): string[] => {
  const totals = new Map<string, number>();
  for (const row of rows) {
    const id = row.account_external_id ?? '';
    if (!id) continue;
    totals.set(id, (totals.get(id) ?? 0) + numeric(row.spend));
  }
  return [...totals.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, n)
    .map(([id]) => id);
};

/**
 * Join campaign-level insights against campaign slice to compute
 * spend-by-objective pie slices.
 */
export const spendByObjective = (
  insights: MetaInsightRecord[],
  campaigns: MetaCampaign[],
): { label: string; value: number }[] => {
  const campaignIdToObjective = new Map<string, string>();
  for (const c of campaigns) {
    campaignIdToObjective.set(c.external_id, c.objective || 'UNKNOWN');
  }
  const totals = new Map<string, number>();
  for (const row of insights) {
    const campaignId = row.campaign_external_id ?? '';
    const objective = campaignIdToObjective.get(campaignId) ?? 'UNKNOWN';
    totals.set(objective, (totals.get(objective) ?? 0) + numeric(row.spend));
  }
  return [...totals.entries()].map(([label, value]) => ({ label, value }));
};

/**
 * Derive ROAS from a row's `actions` array. Returns `null` when no purchase
 * action with a value is present (caller should degrade UI).
 */
export const derivedRoas = (row: MetaInsightRecord): number | null => {
  const actions = row.actions ?? [];
  for (const raw of actions) {
    const action = raw as { action_type?: unknown; value?: unknown };
    const type = typeof action.action_type === 'string' ? action.action_type : '';
    if (type === 'omni_purchase' || type === 'purchase') {
      const value = numeric(action.value);
      const spend = numeric(row.spend);
      if (spend > 0 && value > 0) {
        return value / spend;
      }
    }
  }
  return null;
};

/** Does ANY row have a derivable ROAS value? */
export const hasPurchaseActions = (rows: MetaInsightRecord[]): boolean =>
  rows.some((row) => derivedRoas(row) !== null);

/** Aggregate ROAS across rows that have a purchase value. */
export const aggregatedRoas = (rows: MetaInsightRecord[]): number | null => {
  let purchaseValue = 0;
  let spend = 0;
  let anyPurchase = false;
  for (const row of rows) {
    const actions = row.actions ?? [];
    for (const raw of actions) {
      const action = raw as { action_type?: unknown; value?: unknown };
      const type = typeof action.action_type === 'string' ? action.action_type : '';
      if (type === 'omni_purchase' || type === 'purchase') {
        purchaseValue += numeric(action.value);
        anyPurchase = true;
      }
    }
    spend += numeric(row.spend);
  }
  if (!anyPurchase || spend <= 0) return null;
  return purchaseValue / spend;
};

export interface DualAxisTrendPoint {
  date: string;
  ctr: number;
  cpm: number;
}

/**
 * Group rows by date and compute dual-axis CTR + CPM series for the
 * Insights page trend chart.
 */
export const groupCtrCpmByDate = (rows: MetaInsightRecord[]): DualAxisTrendPoint[] => {
  const byDate = new Map<string, { spend: number; impressions: number; clicks: number }>();
  for (const row of rows) {
    const existing = byDate.get(row.date) ?? { spend: 0, impressions: 0, clicks: 0 };
    existing.spend += numeric(row.spend);
    existing.impressions += numeric(row.impressions);
    existing.clicks += numeric(row.clicks);
    byDate.set(row.date, existing);
  }
  return [...byDate.entries()]
    .map(([date, v]) => ({
      date,
      ctr: v.impressions > 0 ? v.clicks / v.impressions : 0,
      cpm: v.impressions > 0 ? (v.spend / v.impressions) * 1000 : 0,
    }))
    .sort((a, b) => a.date.localeCompare(b.date));
};
