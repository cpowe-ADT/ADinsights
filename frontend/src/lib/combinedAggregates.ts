/**
 * Sprint 4 combined-dashboard client-side aggregates.
 *
 * Keep these pure and side-effect free — they are consumed by
 * PlatformDashboard, CampaignDashboard, and CreativeDashboard to derive
 * cross-platform KPIs without depending on backend changes (§3 data-
 * availability audit: no new endpoints this sprint).
 */

export interface PlatformSumRow {
  platform: string;
  spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  reach?: number;
}

export interface KpiTotals {
  spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  ctr: number; // clicks / impressions (decimal)
  cpm: number; // spend / impressions * 1000
  roas: number; // conversions / spend (not revenue-based)
}

const safeDiv = (numerator: number, denominator: number): number =>
  denominator > 0 && Number.isFinite(numerator / denominator) ? numerator / denominator : 0;

export function totalsFromPlatformRows(rows: PlatformSumRow[]): KpiTotals {
  const totals = rows.reduce(
    (acc, row) => ({
      spend: acc.spend + (Number(row.spend) || 0),
      impressions: acc.impressions + (Number(row.impressions) || 0),
      clicks: acc.clicks + (Number(row.clicks) || 0),
      conversions: acc.conversions + (Number(row.conversions) || 0),
    }),
    { spend: 0, impressions: 0, clicks: 0, conversions: 0 },
  );

  return {
    ...totals,
    ctr: safeDiv(totals.clicks, totals.impressions),
    cpm: safeDiv(totals.spend, totals.impressions) * 1000,
    roas: safeDiv(totals.conversions, totals.spend),
  };
}

export function ctrFromRow(row: { clicks: number; impressions: number }): number {
  return safeDiv(row.clicks, row.impressions);
}

export function cpmFromRow(row: { spend: number; impressions: number }): number {
  return safeDiv(row.spend, row.impressions) * 1000;
}

export function roasFromRow(row: { conversions: number; spend: number }): number {
  return safeDiv(row.conversions, row.spend);
}

/**
 * Top-N rows sorted desc by a numeric metric. Stable — returns a new array.
 */
export function topNBy<T>(rows: T[], metric: (row: T) => number, n: number): T[] {
  return [...rows].sort((a, b) => (Number(metric(b)) || 0) - (Number(metric(a)) || 0)).slice(0, n);
}
