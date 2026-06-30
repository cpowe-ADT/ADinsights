/**
 * Sprint 4 S4b — client-side reducers for GA4 and Search Console rows.
 *
 * The web-analytics pages MUST NOT call /api/metrics/combined/ (R3 rule).
 * They consume their own endpoints (/analytics/web/ga4/ and
 * /analytics/web/search-console/) via `lib/webAnalytics.ts`.
 *
 * These helpers aggregate raw row arrays into the shapes the new viz-kit
 * primitives expect (`TrendLinePoint`, `PieCompositionDatum`, etc.).
 */

import type { GoogleAnalyticsWebRow, SearchConsoleWebRow } from './webAnalytics';

// -----------------------------------------------------------------------------
// GA4
// -----------------------------------------------------------------------------

export interface Ga4Totals {
  sessions: number;
  engagedSessions: number;
  conversions: number;
  purchaseRevenue: number;
  /** Engagement rate weighted by sessions. */
  engagementRate: number;
}

export function aggregateGa4Totals(rows: GoogleAnalyticsWebRow[]): Ga4Totals {
  let sessions = 0;
  let engagedSessions = 0;
  let conversions = 0;
  let purchaseRevenue = 0;
  for (const row of rows) {
    sessions += Number(row.sessions || 0);
    engagedSessions += Number(row.engaged_sessions || 0);
    conversions += Number(row.conversions || 0);
    purchaseRevenue += Number(row.purchase_revenue || 0);
  }
  const engagementRate = sessions > 0 ? engagedSessions / sessions : 0;
  return { sessions, engagedSessions, conversions, purchaseRevenue, engagementRate };
}

export interface Ga4TrendPoint {
  date: string;
  sessions: number;
  conversions: number;
  [key: string]: string | number | null | undefined;
}

export function aggregateGa4TrendByDay(rows: GoogleAnalyticsWebRow[]): Ga4TrendPoint[] {
  const buckets = new Map<string, Ga4TrendPoint>();
  for (const row of rows) {
    const date = row.date_day;
    if (!date) continue;
    const existing = buckets.get(date) ?? { date, sessions: 0, conversions: 0 };
    existing.sessions += Number(row.sessions || 0);
    existing.conversions += Number(row.conversions || 0);
    buckets.set(date, existing);
  }
  return Array.from(buckets.values()).sort((a, b) => a.date.localeCompare(b.date));
}

export interface Ga4ChannelDatum {
  channel: string;
  sessions: number;
  conversions: number;
  purchaseRevenue: number;
  engagementRate: number;
}

export function aggregateGa4ByChannel(rows: GoogleAnalyticsWebRow[]): Ga4ChannelDatum[] {
  const buckets = new Map<string, Ga4ChannelDatum & { _engagedSessions: number }>();
  for (const row of rows) {
    const channel = row.channel_group?.trim() || 'Unassigned';
    const existing = buckets.get(channel) ?? {
      channel,
      sessions: 0,
      conversions: 0,
      purchaseRevenue: 0,
      engagementRate: 0,
      _engagedSessions: 0,
    };
    existing.sessions += Number(row.sessions || 0);
    existing.conversions += Number(row.conversions || 0);
    existing.purchaseRevenue += Number(row.purchase_revenue || 0);
    existing._engagedSessions += Number(row.engaged_sessions || 0);
    buckets.set(channel, existing);
  }
  return Array.from(buckets.values())
    .map(({ _engagedSessions, ...rest }) => ({
      ...rest,
      engagementRate: rest.sessions > 0 ? _engagedSessions / rest.sessions : 0,
    }))
    .sort((a, b) => b.sessions - a.sessions);
}

// -----------------------------------------------------------------------------
// Search Console
// -----------------------------------------------------------------------------

export interface SearchConsoleTotals {
  clicks: number;
  impressions: number;
  /** CTR aggregated as total clicks / total impressions. */
  ctr: number;
  /** Position weighted by impressions. */
  avgPosition: number;
}

export function aggregateSearchConsoleTotals(rows: SearchConsoleWebRow[]): SearchConsoleTotals {
  let clicks = 0;
  let impressions = 0;
  let weightedPositionNumerator = 0;
  for (const row of rows) {
    const rowClicks = Number(row.clicks || 0);
    const rowImpr = Number(row.impressions || 0);
    const rowPosition = Number(row.position || 0);
    clicks += rowClicks;
    impressions += rowImpr;
    weightedPositionNumerator += rowPosition * rowImpr;
  }
  const ctr = impressions > 0 ? clicks / impressions : 0;
  const avgPosition = impressions > 0 ? weightedPositionNumerator / impressions : 0;
  return { clicks, impressions, ctr, avgPosition };
}

export interface SearchConsoleTrendPoint {
  date: string;
  clicks: number;
  impressions: number;
  [key: string]: string | number | null | undefined;
}

export function aggregateSearchConsoleTrendByDay(
  rows: SearchConsoleWebRow[],
): SearchConsoleTrendPoint[] {
  const buckets = new Map<string, SearchConsoleTrendPoint>();
  for (const row of rows) {
    const date = row.date_day;
    if (!date) continue;
    const existing = buckets.get(date) ?? { date, clicks: 0, impressions: 0 };
    existing.clicks += Number(row.clicks || 0);
    existing.impressions += Number(row.impressions || 0);
    buckets.set(date, existing);
  }
  return Array.from(buckets.values()).sort((a, b) => a.date.localeCompare(b.date));
}

export interface SearchConsoleDeviceDatum {
  device: string;
  clicks: number;
  impressions: number;
}

export function aggregateSearchConsoleByDevice(
  rows: SearchConsoleWebRow[],
): SearchConsoleDeviceDatum[] {
  const buckets = new Map<string, SearchConsoleDeviceDatum>();
  for (const row of rows) {
    const device = (row.device || 'unknown').toLowerCase();
    const existing = buckets.get(device) ?? { device, clicks: 0, impressions: 0 };
    existing.clicks += Number(row.clicks || 0);
    existing.impressions += Number(row.impressions || 0);
    buckets.set(device, existing);
  }
  return Array.from(buckets.values()).sort((a, b) => b.clicks - a.clicks);
}

export interface SearchConsoleQueryRow extends SearchConsoleDeviceDatum {
  query: string;
  ctr: number;
  avgPosition: number;
}

export function aggregateSearchConsoleTopQueries(
  rows: SearchConsoleWebRow[],
  limit = 50,
): SearchConsoleQueryRow[] {
  const buckets = new Map<string, SearchConsoleQueryRow & { _positionWeightedSum: number }>();
  for (const row of rows) {
    const query = row.query?.trim() || '(unspecified)';
    const existing = buckets.get(query) ?? {
      query,
      device: '',
      clicks: 0,
      impressions: 0,
      ctr: 0,
      avgPosition: 0,
      _positionWeightedSum: 0,
    };
    const rowClicks = Number(row.clicks || 0);
    const rowImpr = Number(row.impressions || 0);
    existing.clicks += rowClicks;
    existing.impressions += rowImpr;
    existing._positionWeightedSum += Number(row.position || 0) * rowImpr;
    buckets.set(query, existing);
  }
  return Array.from(buckets.values())
    .map(({ _positionWeightedSum, ...rest }) => ({
      ...rest,
      ctr: rest.impressions > 0 ? rest.clicks / rest.impressions : 0,
      avgPosition: rest.impressions > 0 ? _positionWeightedSum / rest.impressions : 0,
    }))
    .sort((a, b) => b.clicks - a.clicks)
    .slice(0, limit);
}
