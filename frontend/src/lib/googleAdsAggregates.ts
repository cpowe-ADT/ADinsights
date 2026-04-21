/**
 * Pure aggregation + derivation helpers for the Google Ads workspace tabs.
 *
 * Extracted per Sprint 3 architect design §4/§6 to keep tab sections lean
 * and provide a stable test surface. No React, no store access — callers
 * pass plain records.
 *
 * Naming mirrors `metaAggregates.ts`. Divide-safe math everywhere.
 */
import type { BubbleShape } from '../components/viz/BubbleScatter';

export type GoogleAdsChannelType =
  | 'SEARCH'
  | 'DISPLAY'
  | 'VIDEO'
  | 'PERFORMANCE_MAX'
  | 'SHOPPING'
  | string;

export interface GoogleAdsCampaignRow {
  campaign_id?: string | number;
  campaign_name?: string;
  campaign_status?: string;
  channel_type?: string;
  spend?: number;
  clicks?: number;
  impressions?: number;
  conversions?: number;
  conversion_value?: number;
  roas?: number;
  cpa?: number;
  [key: string]: unknown;
}

export interface GoogleAdsKeywordRow {
  keyword_text?: string;
  keyword?: string;
  match_type?: string;
  keyword_status?: string;
  quality_score?: number | null;
  impressions?: number;
  clicks?: number;
  conversions?: number;
  spend?: number;
  cpa?: number;
  [key: string]: unknown;
}

export interface GoogleAdsSearchTermRow {
  search_term?: string;
  search_term_text?: string;
  impressions?: number;
  clicks?: number;
  conversions?: number;
  spend?: number;
  cpa?: number;
  [key: string]: unknown;
}

export interface GoogleAdsOverviewKpis {
  spend: number;
  conversions: number;
  cpa: number;
  roas: number;
}

export interface GoogleAdsCampaignKpis {
  totalSpend: number;
  totalConversions: number;
  avgCpa: number;
  avgRoas: number;
}

export interface GoogleAdsKeywordKpis {
  count: number;
  avgQualityScore: number | null;
  topConversions: number;
}

export interface GoogleAdsBubblePoint {
  id: string;
  label: string;
  x: number;
  y: number;
  z: number;
  shape: BubbleShape;
}

export interface GoogleAdsBarDatum {
  label: string;
  value: number;
}

export interface GoogleAdsTrendPoint {
  date: string;
  spend: number;
  conversions: number;
  // Index signature keeps this assignable to viz-kit TrendLinePoint.
  [key: string]: string | number | null | undefined;
}

/** Coerce an unknown to a finite number (0 on failure). */
export const toNumber = (value: unknown): number => {
  if (value === null || value === undefined || value === '') return 0;
  const n = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(n) ? n : 0;
};

/** Divide-safe ratio — returns 0 if denominator is zero/nan. */
export const safeDivide = (num: number, denom: number): number => {
  if (!denom || !Number.isFinite(denom)) return 0;
  const v = num / denom;
  return Number.isFinite(v) ? v : 0;
};

/**
 * Overview KPI rollup.
 * Uses payload `metrics` directly when present; falls back to row sums.
 *
 * Architect §4: IS% is NOT available — only 4 tiles ship.
 */
export const rollupOverviewKpis = (
  summary: {
    metrics?: Record<string, unknown>;
  } | null | undefined,
): GoogleAdsOverviewKpis => {
  const m = summary?.metrics ?? {};
  const spend = toNumber(m.spend);
  const conversions = toNumber(m.conversions);
  const cpa = toNumber(m.cpa) || safeDivide(spend, conversions);
  const roas = toNumber(m.roas);
  return { spend, conversions, cpa, roas };
};

/**
 * Derive a Recharts trend series from `summary.trend[]` for dual-axis
 * (spend left, conversions right). Accepts mixed string/number records.
 */
export const deriveTrendSeries = (
  trend: Array<Record<string, unknown>> | undefined | null,
): GoogleAdsTrendPoint[] => {
  if (!trend || trend.length === 0) return [];
  return trend
    .map((row) => ({
      date: String(row.date ?? ''),
      spend: toNumber(row.spend),
      conversions: toNumber(row.conversions),
    }))
    .filter((p) => p.date !== '')
    .sort((a, b) => a.date.localeCompare(b.date));
};

/**
 * Architect §4 §6.1: channel-pie is derived from the campaigns-tab cache,
 * NOT from the workspace summary. Falls back to empty array so the
 * caller can render EmptyState with `no_data_for_range`.
 */
export const buildChannelPie = (
  rows: GoogleAdsCampaignRow[] | undefined | null,
): GoogleAdsBarDatum[] => {
  if (!rows || rows.length === 0) return [];
  const totals = new Map<string, number>();
  for (const row of rows) {
    const channel = (row.channel_type ?? 'OTHER').toString().toUpperCase() || 'OTHER';
    totals.set(channel, (totals.get(channel) ?? 0) + toNumber(row.spend));
  }
  return [...totals.entries()]
    .filter(([, v]) => v > 0)
    .map(([label, value]) => ({ label, value }))
    .sort((a, b) => b.value - a.value);
};

/**
 * Campaign KPIs — architect §6.2. Avg CPA/ROAS are spend-weighted
 * (total spend / total conversions and total conv value / total spend
 * respectively) rather than arithmetic average over rows, which is the
 * user-meaningful aggregation.
 */
export const rollupCampaignKpis = (
  rows: GoogleAdsCampaignRow[] | undefined | null,
): GoogleAdsCampaignKpis => {
  if (!rows || rows.length === 0) {
    return { totalSpend: 0, totalConversions: 0, avgCpa: 0, avgRoas: 0 };
  }
  let totalSpend = 0;
  let totalConversions = 0;
  let totalConvValue = 0;
  for (const row of rows) {
    totalSpend += toNumber(row.spend);
    totalConversions += toNumber(row.conversions);
    totalConvValue += toNumber(row.conversion_value);
  }
  const avgCpa = safeDivide(totalSpend, totalConversions);
  const avgRoas = safeDivide(totalConvValue, totalSpend);
  return { totalSpend, totalConversions, avgCpa, avgRoas };
};

/** Architect-confirmed shape mapping for BubbleScatter over channel type. */
export const channelTypeToBubbleShape = (channelType: unknown): BubbleShape => {
  const s = typeof channelType === 'string' ? channelType.toUpperCase() : '';
  if (s === 'SEARCH') return 'circle';
  if (s === 'DISPLAY') return 'triangle';
  if (s === 'VIDEO') return 'square';
  // Kit only exports three shapes (circle/triangle/square). Map the
  // remaining Google Ads channel types onto those three. Architect §6.2
  // originally specified diamond/cross; shape mapping here degrades
  // gracefully until the kit grows more shapes (no regression).
  if (s === 'PERFORMANCE_MAX' || s === 'SHOPPING') return 'square';
  return 'circle';
};

/** Build bubbles for the campaigns scatter chart (x=spend, y=conv_rate, z=impressions). */
export const buildCampaignBubblePoints = (
  rows: GoogleAdsCampaignRow[] | undefined | null,
): GoogleAdsBubblePoint[] => {
  if (!rows || rows.length === 0) return [];
  return rows
    .map((row, idx) => {
      const clicks = toNumber(row.clicks);
      const conversions = toNumber(row.conversions);
      const spend = toNumber(row.spend);
      const impressions = toNumber(row.impressions);
      const convRate = safeDivide(conversions, clicks);
      const id = String(row.campaign_id ?? `row-${idx}`);
      return {
        id,
        label: String(row.campaign_name ?? id),
        x: spend,
        y: convRate,
        z: impressions,
        shape: channelTypeToBubbleShape(row.channel_type),
      };
    })
    .filter((p) => p.x > 0 || p.y > 0 || p.z > 0);
};

/**
 * Architect §6.2 — per-campaign daily trend is NOT available. Fallback
 * is top-10 campaigns by spend, rendered as a DistributionBar.
 */
export const buildTopSpendBars = (
  rows: GoogleAdsCampaignRow[] | undefined | null,
  limit = 10,
): GoogleAdsBarDatum[] => {
  if (!rows || rows.length === 0) return [];
  return [...rows]
    .map((row, idx) => ({
      label: String(row.campaign_name ?? row.campaign_id ?? `row-${idx}`),
      value: toNumber(row.spend),
    }))
    .filter((d) => d.value > 0)
    .sort((a, b) => b.value - a.value)
    .slice(0, Math.max(1, limit));
};

/**
 * Search KPIs — architect §6.3. Avg Quality Score is the arithmetic
 * mean of rows with a finite QS (nulls dropped); returns `null` when no
 * row has QS so KpiTile can render no-data.
 */
export const rollupKeywordKpis = (
  rows: GoogleAdsKeywordRow[] | undefined | null,
): GoogleAdsKeywordKpis => {
  if (!rows || rows.length === 0) {
    return { count: 0, avgQualityScore: null, topConversions: 0 };
  }
  let qsSum = 0;
  let qsCount = 0;
  let topConversions = 0;
  for (const row of rows) {
    const qs = row.quality_score;
    if (qs !== null && qs !== undefined && Number.isFinite(Number(qs))) {
      qsSum += Number(qs);
      qsCount += 1;
    }
    const conv = toNumber(row.conversions);
    if (conv > topConversions) topConversions = conv;
  }
  return {
    count: rows.length,
    avgQualityScore: qsCount > 0 ? qsSum / qsCount : null,
    topConversions,
  };
};

/** Match-type shape encoding for the search bubble scatter. */
export const matchTypeToBubbleShape = (matchType: unknown): BubbleShape => {
  const s = typeof matchType === 'string' ? matchType.toUpperCase() : '';
  if (s === 'EXACT') return 'circle';
  if (s === 'PHRASE') return 'triangle';
  if (s === 'BROAD') return 'square';
  return 'circle';
};

/** x=quality_score, y=cpc, z=impressions for keyword bubble. */
export const buildQsCpcBubblePoints = (
  rows: GoogleAdsKeywordRow[] | undefined | null,
): GoogleAdsBubblePoint[] => {
  if (!rows || rows.length === 0) return [];
  return rows
    .map((row, idx) => {
      const qs = toNumber(row.quality_score);
      const spend = toNumber(row.spend);
      const clicks = toNumber(row.clicks);
      const cpc = safeDivide(spend, clicks);
      const impressions = toNumber(row.impressions);
      const label = String(row.keyword_text ?? row.keyword ?? `row-${idx}`);
      return {
        id: `kw-${idx}-${label}`,
        label,
        x: qs,
        y: cpc,
        z: impressions,
        shape: matchTypeToBubbleShape(row.match_type),
      };
    })
    .filter((p) => p.x > 0 || p.y > 0 || p.z > 0);
};

/** Top-N search terms by conversions (architect §6.3). */
export const topSearchTermsByConv = (
  rows: GoogleAdsSearchTermRow[] | undefined | null,
  limit = 10,
): GoogleAdsBarDatum[] => {
  if (!rows || rows.length === 0) return [];
  return [...rows]
    .map((row, idx) => ({
      label: String(row.search_term ?? row.search_term_text ?? `row-${idx}`),
      value: toNumber(row.conversions),
    }))
    .filter((d) => d.value > 0)
    .sort((a, b) => b.value - a.value)
    .slice(0, Math.max(1, limit));
};

/**
 * Architect §6.8 change-log severity derivation.
 * CREATE → info, UPDATE → warning, REMOVE → danger.
 */
export type ChangeSeverity = 'info' | 'warning' | 'danger';
export const deriveChangeSeverity = (operation: unknown): ChangeSeverity => {
  const op = typeof operation === 'string' ? operation.toUpperCase() : '';
  if (op === 'REMOVE' || op === 'REMOVED' || op === 'DELETE') return 'danger';
  if (op === 'UPDATE' || op === 'UPDATED' || op === 'MODIFY') return 'warning';
  return 'info';
};

/**
 * Architect §6.2 campaign status → severity/chip tone mapping.
 * Kept here so both CampaignsTabSection and the legacy page share
 * the exact same chip classification.
 */
export type StatusTone = 'success' | 'warning' | 'danger' | 'neutral';
export const deriveCampaignStatusTone = (status: unknown): StatusTone => {
  const s = typeof status === 'string' ? status.toUpperCase() : '';
  if (s === 'ENABLED' || s === 'ACTIVE') return 'success';
  if (s === 'PAUSED') return 'warning';
  if (s === 'REMOVED' || s === 'ENDED' || s === 'DISAPPROVED') return 'danger';
  return 'neutral';
};

// -----------------------------------------------------------------------------
// Pacing helpers — architect §6.7
// -----------------------------------------------------------------------------

export interface GoogleAdsPacingPayload {
  month?: string;
  spend_mtd?: number;
  budget_month?: number;
  forecast_month_end?: number;
  over_under?: number;
  runway_days?: number | null;
  pacing_pct?: number;
  alerts?: {
    overspend_risk?: boolean;
    underdelivery?: boolean;
  };
  [key: string]: unknown;
}

export interface GoogleAdsPacingKpis {
  spendMtd: number;
  budgetMonth: number;
  forecast: number;
  overUnder: number;
}

/**
 * Architect §6.7: if the backend doesn't expose `pacing_pct` at the top
 * of `/budgets/pacing/`, compute it from `spend_mtd / budget_month` with
 * divide-safe math. Returns `null` when denominator is zero so callers
 * can render the gauge empty state.
 */
export const derivePacingPct = (
  pacing: GoogleAdsPacingPayload | null | undefined,
): number | null => {
  if (!pacing) return null;
  const direct = pacing.pacing_pct;
  if (direct !== undefined && direct !== null && Number.isFinite(Number(direct))) {
    return Number(direct);
  }
  const spend = toNumber(pacing.spend_mtd);
  const budget = toNumber(pacing.budget_month);
  if (budget <= 0) return null;
  return safeDivide(spend, budget);
};

export const rollupPacingKpis = (
  pacing: GoogleAdsPacingPayload | null | undefined,
): GoogleAdsPacingKpis => {
  const spendMtd = toNumber(pacing?.spend_mtd);
  const budgetMonth = toNumber(pacing?.budget_month);
  const forecast = toNumber(pacing?.forecast_month_end);
  const overUnder = toNumber(pacing?.over_under);
  return { spendMtd, budgetMonth, forecast, overUnder };
};

// -----------------------------------------------------------------------------
// Change-log helpers — architect §6.8
// -----------------------------------------------------------------------------

export interface GoogleAdsChangeRow {
  customer_id?: string | number;
  change_date_time?: string;
  user_email?: string;
  client_type?: string;
  change_resource_type?: string;
  resource_change_operation?: string;
  campaign_id?: string | number;
  ad_group_id?: string | number;
  ad_id?: string | number;
  changed_fields?: unknown;
  [key: string]: unknown;
}

/** Group by change_resource_type and return counts for DistributionBar. */
export const groupChangesByResourceType = (
  rows: GoogleAdsChangeRow[] | undefined | null,
): GoogleAdsBarDatum[] => {
  if (!rows || rows.length === 0) return [];
  const totals = new Map<string, number>();
  for (const row of rows) {
    const key = (row.change_resource_type ?? 'OTHER').toString().toUpperCase() || 'OTHER';
    totals.set(key, (totals.get(key) ?? 0) + 1);
  }
  return [...totals.entries()]
    .map(([label, value]) => ({ label, value }))
    .sort((a, b) => b.value - a.value);
};

/** Count rows whose change_date_time is within the last 7 days. */
export const countChanges7d = (
  rows: GoogleAdsChangeRow[] | undefined | null,
  now: Date = new Date(),
): number => {
  if (!rows || rows.length === 0) return 0;
  const cutoff = now.getTime() - 7 * 24 * 60 * 60 * 1000;
  let count = 0;
  for (const row of rows) {
    const raw = row.change_date_time;
    if (!raw) continue;
    const ts = Date.parse(String(raw));
    if (Number.isFinite(ts) && ts >= cutoff) count += 1;
  }
  return count;
};

// -----------------------------------------------------------------------------
// Recommendations helpers — architect §6.9
// -----------------------------------------------------------------------------

export interface GoogleAdsRecommendationRow {
  customer_id?: string | number;
  recommendation_type?: string;
  resource_name?: string;
  campaign_id?: string | number;
  ad_group_id?: string | number;
  dismissed?: boolean;
  impact_metadata?: unknown;
  last_seen_at?: string;
  [key: string]: unknown;
}

export interface GoogleAdsRecommendationKpis {
  active: number;
  dismissed: number;
}

/**
 * Architect §6.9: recommendation severity lives in untyped
 * `impact_metadata` JSON. Use `impact_metadata?.severity` first, then
 * fall back to a recommendation_type heuristic.
 *
 * Heuristic fallback map (documented for future SDK drift mitigation):
 *   - BUDGET / BID / KEYWORD_BUDGET → warning (monetary guardrails)
 *   - POLICY / DISAPPROVED / FORECASTING_SET_TARGET_* → danger
 *   - TEXT_AD / RESPONSIVE_SEARCH_AD / ADD_ASSET / CREATIVE → info
 *   - everything else → info
 */
export type RecommendationSeverity = 'info' | 'warning' | 'danger';

const WARNING_TYPE_PATTERNS = ['BUDGET', 'BID', 'PACING'];
const DANGER_TYPE_PATTERNS = ['POLICY', 'DISAPPROVED', 'SUSPENDED', 'PAUSED_ACCOUNT'];

export const deriveRecommendationSeverity = (
  row: GoogleAdsRecommendationRow | null | undefined,
): RecommendationSeverity => {
  if (!row) return 'info';
  // Preferred: explicit severity inside the untyped impact_metadata JSON.
  try {
    const meta = row.impact_metadata;
    if (meta && typeof meta === 'object') {
      const sev = (meta as Record<string, unknown>).severity;
      if (typeof sev === 'string') {
        const norm = sev.toUpperCase();
        if (norm === 'DANGER' || norm === 'CRITICAL' || norm === 'HIGH') return 'danger';
        if (norm === 'WARNING' || norm === 'MEDIUM') return 'warning';
        if (norm === 'INFO' || norm === 'LOW') return 'info';
      }
    }
  } catch {
    // Fall through to heuristic.
  }
  const t = typeof row.recommendation_type === 'string' ? row.recommendation_type.toUpperCase() : '';
  if (!t) return 'info';
  if (DANGER_TYPE_PATTERNS.some((p) => t.includes(p))) return 'danger';
  if (WARNING_TYPE_PATTERNS.some((p) => t.includes(p))) return 'warning';
  return 'info';
};

export const rollupRecommendationKpis = (
  rows: GoogleAdsRecommendationRow[] | undefined | null,
): GoogleAdsRecommendationKpis => {
  if (!rows || rows.length === 0) return { active: 0, dismissed: 0 };
  let active = 0;
  let dismissed = 0;
  for (const row of rows) {
    if (row.dismissed) dismissed += 1;
    else active += 1;
  }
  return { active, dismissed };
};

/** Count by recommendation_type for PieComposition. */
export const groupRecommendationsByType = (
  rows: GoogleAdsRecommendationRow[] | undefined | null,
): GoogleAdsBarDatum[] => {
  if (!rows || rows.length === 0) return [];
  const totals = new Map<string, number>();
  for (const row of rows) {
    const key = (row.recommendation_type ?? 'OTHER').toString() || 'OTHER';
    totals.set(key, (totals.get(key) ?? 0) + 1);
  }
  return [...totals.entries()]
    .map(([label, value]) => ({ label, value }))
    .sort((a, b) => b.value - a.value);
};

/**
 * Architect §6.9: impact_metadata is arbitrary JSON. Pluck known keys
 * (primary_metric / impact_percentage / description). Falls back to a
 * short JSON preview so the cell never renders blank when data exists.
 */
export const formatRecommendationImpact = (
  row: GoogleAdsRecommendationRow | null | undefined,
): string => {
  if (!row) return '—';
  const meta = row.impact_metadata;
  if (!meta || typeof meta !== 'object') return '—';
  const m = meta as Record<string, unknown>;
  const pieces: string[] = [];
  if (typeof m.primary_metric === 'string' && m.primary_metric) {
    pieces.push(String(m.primary_metric));
  }
  if (m.impact_percentage !== undefined && m.impact_percentage !== null) {
    const pct = Number(m.impact_percentage);
    if (Number.isFinite(pct)) pieces.push(`${(pct * 100).toFixed(1)}%`);
  }
  if (typeof m.description === 'string' && m.description) {
    pieces.push(String(m.description));
  }
  if (pieces.length > 0) return pieces.join(' · ');
  try {
    const json = JSON.stringify(meta);
    return json.length > 80 ? `${json.slice(0, 77)}…` : json;
  } catch {
    return '—';
  }
};

// -----------------------------------------------------------------------------
// Reports helpers — architect §6.10
// -----------------------------------------------------------------------------

export type ExportJobStatusTone = 'success' | 'warning' | 'danger' | 'neutral';

export const deriveExportJobStatusTone = (status: unknown): ExportJobStatusTone => {
  const s = typeof status === 'string' ? status.toLowerCase() : '';
  if (s === 'complete' || s === 'completed' || s === 'success' || s === 'succeeded') return 'success';
  if (s === 'running' || s === 'queued' || s === 'pending' || s === 'in_progress') return 'warning';
  if (s === 'failed' || s === 'error' || s === 'errored' || s === 'cancelled') return 'danger';
  return 'neutral';
};
