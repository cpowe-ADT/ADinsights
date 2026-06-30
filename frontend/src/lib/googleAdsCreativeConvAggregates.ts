/**
 * S3b-CreativeConv helpers — Assets / PMax / Conversions tab aggregations.
 *
 * Kept in a separate module from `googleAdsAggregates.ts` (owned by S3a) so
 * that S3b can ship without touching the S3a helper file. If these ever
 * grow into shared surfaces, the two modules can be merged post-sprint.
 *
 * Pure functions — no React, no store access — caller passes plain records.
 */
import { safeDivide, toNumber } from './googleAdsAggregates';

export interface GoogleAdsAssetRow {
  asset_id?: string | number;
  asset_type?: string;
  asset_text?: string;
  asset_name?: string;
  policy_approval_status?: string;
  impressions?: number;
  clicks?: number;
  conversions?: number;
  cpa?: number;
  [key: string]: unknown;
}

export interface GoogleAdsAssetGroupRow {
  asset_group_id?: string | number;
  asset_group_name?: string;
  asset_group_status?: string;
  spend?: number;
  impressions?: number;
  clicks?: number;
  conversions?: number;
  conversion_value?: number;
  cpa?: number;
  roas?: number;
  [key: string]: unknown;
}

export interface GoogleAdsConversionActionRow {
  conversion_action_id?: string | number;
  conversion_action_name?: string;
  conversions?: number;
  value?: number;
  conversion_value?: number;
  all_conversions?: number;
  cpa?: number;
  spend?: number;
  [key: string]: unknown;
}

// -------- Assets --------

export interface GoogleAdsAssetKpis {
  total: number;
  disapproved: number;
  topAssetConv: number;
}

export const rollupAssetKpis = (
  rows: GoogleAdsAssetRow[] | undefined | null,
): GoogleAdsAssetKpis => {
  if (!rows || rows.length === 0) {
    return { total: 0, disapproved: 0, topAssetConv: 0 };
  }
  let disapproved = 0;
  let topAssetConv = 0;
  for (const row of rows) {
    const status = (row.policy_approval_status ?? '').toString().toUpperCase();
    if (status === 'DISAPPROVED' || status === 'AREA_OF_INTEREST_ONLY') {
      disapproved += 1;
    }
    const conv = toNumber(row.conversions);
    if (conv > topAssetConv) topAssetConv = conv;
  }
  return { total: rows.length, disapproved, topAssetConv };
};

export interface GoogleAdsLabelValue {
  label: string;
  value: number;
}

/** Count of assets by asset_type — fuels the asset-type PieComposition. */
export const buildAssetTypePie = (
  rows: GoogleAdsAssetRow[] | undefined | null,
): GoogleAdsLabelValue[] => {
  if (!rows || rows.length === 0) return [];
  const totals = new Map<string, number>();
  for (const row of rows) {
    const type = (row.asset_type ?? 'UNKNOWN').toString().toUpperCase() || 'UNKNOWN';
    totals.set(type, (totals.get(type) ?? 0) + 1);
  }
  return [...totals.entries()]
    .map(([label, value]) => ({ label, value }))
    .sort((a, b) => b.value - a.value);
};

export type HeatTone = 'low' | 'medium' | 'high';

/** Non-color tone chip for the heat-tinted asset grid. */
export const deriveHeatTone = (ratio: number): HeatTone => {
  if (!Number.isFinite(ratio) || ratio <= 0) return 'low';
  if (ratio < 0.33) return 'low';
  if (ratio < 0.66) return 'medium';
  return 'high';
};

export interface HeatGridCell {
  id: string;
  title: string;
  subtitle: string;
  convRate: number;
  /** Normalized intensity [0, 1] for alpha/opacity mapping. */
  intensity: number;
  tone: HeatTone;
  impressions: number;
  clicks: number;
  conversions: number;
}

/**
 * Build the heat-tinted asset grid cells.
 *
 * Architect §5 / §6.4 confirmed per-asset daily series is NOT available in
 * the API contract, so the heat tint is driven by conversion_rate (a
 * single-metric encoding). `resolveSeriesColor(0)` supplies the base blue;
 * the consumer component applies `intensity` as alpha.
 */
export const buildAssetHeatGrid = (
  rows: GoogleAdsAssetRow[] | undefined | null,
): HeatGridCell[] => {
  if (!rows || rows.length === 0) return [];
  const cells = rows.map((row, idx) => {
    const clicks = toNumber(row.clicks);
    const conversions = toNumber(row.conversions);
    const impressions = toNumber(row.impressions);
    const convRate = safeDivide(conversions, clicks);
    const title = String(row.asset_name ?? row.asset_text ?? row.asset_id ?? `asset-${idx}`);
    const subtitle = String(row.asset_type ?? 'UNKNOWN');
    return {
      id: String(row.asset_id ?? `asset-${idx}`),
      title,
      subtitle,
      convRate,
      intensity: 0, // filled below after we know the max
      tone: 'low' as HeatTone,
      impressions,
      clicks,
      conversions,
    };
  });
  const max = cells.reduce((m, c) => (c.convRate > m ? c.convRate : m), 0);
  if (max <= 0) return cells;
  return cells.map((c) => {
    const ratio = c.convRate / max;
    return { ...c, intensity: ratio, tone: deriveHeatTone(ratio) };
  });
};

// -------- PMax --------

export interface GoogleAdsPmaxKpis {
  totalGroups: number;
  totalCost: number;
  totalConversions: number;
}

export const rollupPmaxKpis = (
  rows: GoogleAdsAssetGroupRow[] | undefined | null,
): GoogleAdsPmaxKpis => {
  if (!rows || rows.length === 0) {
    return { totalGroups: 0, totalCost: 0, totalConversions: 0 };
  }
  let totalCost = 0;
  let totalConversions = 0;
  for (const row of rows) {
    totalCost += toNumber(row.spend);
    totalConversions += toNumber(row.conversions);
  }
  return { totalGroups: rows.length, totalCost, totalConversions };
};

export interface TreemapDatum {
  name: string;
  spend: number;
  roas: number;
}

/** Architect §6.5: `{ name, spend, roas }` — no opacity derivation here
 *  because `AssetGroupTreemap` applies the roas→opacity clamp internally. */
export const buildPmaxTreemapData = (
  rows: GoogleAdsAssetGroupRow[] | undefined | null,
): TreemapDatum[] => {
  if (!rows || rows.length === 0) return [];
  return rows
    .map((row, idx) => ({
      name: String(row.asset_group_name ?? row.asset_group_id ?? `group-${idx}`),
      spend: toNumber(row.spend),
      roas: toNumber(row.roas),
    }))
    .filter((d) => d.spend > 0);
};

// -------- Conversions --------

export interface GoogleAdsConversionKpis {
  totalConversions: number;
  totalValue: number;
  avgCpa: number;
}

export const rollupConversionKpis = (
  rows: GoogleAdsConversionActionRow[] | undefined | null,
): GoogleAdsConversionKpis => {
  if (!rows || rows.length === 0) {
    return { totalConversions: 0, totalValue: 0, avgCpa: 0 };
  }
  let totalConversions = 0;
  let totalValue = 0;
  let totalSpend = 0;
  for (const row of rows) {
    totalConversions += toNumber(row.conversions);
    totalValue += toNumber(row.value ?? row.conversion_value);
    totalSpend += toNumber(row.spend);
  }
  const avgCpa = safeDivide(totalSpend, totalConversions);
  return { totalConversions, totalValue, avgCpa };
};

/**
 * Architect §6.6 — Funnel stages from workspace summary metrics. Stage
 * order is preserved by the caller (use `DistributionBar` with the
 * data as-provided; ordering is the funnel's semantic backbone).
 */
export const buildFunnelStages = (
  metrics: Record<string, unknown> | undefined | null,
): GoogleAdsLabelValue[] => {
  const m = metrics ?? {};
  const impressions = toNumber(m.impressions);
  const clicks = toNumber(m.clicks);
  const conversions = toNumber(m.conversions);
  // Preserve the ordered stages even if values are zero — the visual
  // needs the stages to be present so users see the drop-off shape.
  return [
    { label: 'Impressions', value: impressions },
    { label: 'Clicks', value: clicks },
    { label: 'Conversions', value: conversions },
  ];
};

/** Architect §6.6 — source-mix pie by conversion_action_name. */
export const buildConvActionPie = (
  rows: GoogleAdsConversionActionRow[] | undefined | null,
): GoogleAdsLabelValue[] => {
  if (!rows || rows.length === 0) return [];
  const totals = new Map<string, number>();
  for (const row of rows) {
    const name = String(row.conversion_action_name ?? 'Unknown');
    totals.set(name, (totals.get(name) ?? 0) + toNumber(row.conversions));
  }
  return [...totals.entries()]
    .filter(([, v]) => v > 0)
    .map(([label, value]) => ({ label, value }))
    .sort((a, b) => b.value - a.value);
};
