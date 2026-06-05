import { PLATFORM_CHART_TOKENS } from '../styles/chartTheme';

/**
 * Sprint 4 shared platform helpers.
 *
 * Extracted from `PlatformDashboard.tsx` (FP-PLAT-03 — top-2 by spend label
 * derivation) so every combined dashboard (Platforms / Campaigns / Creatives)
 * renders platform chips and legends consistently.
 */

/**
 * Capitalize platform slug into a human-friendly label.
 *
 * Preserves the Sprint 2 FP-PLAT-03 behavior:
 *   - Empty/falsy value → em-dash
 *   - `meta_ads` → `Meta Ads`
 *   - `facebook` → `Facebook`
 *   - `GOOGLE` → `GOOGLE` (already uppercase short chunk preserved)
 */
export function formatPlatformLabel(value: string | null | undefined): string {
  if (!value) return '—';
  return value
    .split(/[\s_-]+/)
    .filter(Boolean)
    .map((chunk) =>
      chunk.length <= 3
        ? chunk.toUpperCase()
        : chunk.charAt(0).toUpperCase() + chunk.slice(1).toLowerCase(),
    )
    .join(' ');
}

type PlatformToken = keyof typeof PLATFORM_CHART_TOKENS;

/**
 * Resolve a stable color for a platform slug from the PLATFORM_CHART_TOKENS
 * palette. Falls back to the peer-average gray for unknown platforms.
 *
 * Accepts loose slugs like `facebook` / `instagram` (both map to Meta) and
 * `google` / `google_ads` (both map to Google Ads).
 */
export function platformColor(platform: string | null | undefined): string {
  if (!platform) return PLATFORM_CHART_TOKENS.peer_avg;
  const slug = platform.toLowerCase().trim();

  // Direct match on token keys first.
  if (slug in PLATFORM_CHART_TOKENS) {
    return PLATFORM_CHART_TOKENS[slug as PlatformToken];
  }

  // Meta family → meta_ads color.
  if (slug === 'meta' || slug === 'facebook' || slug === 'instagram' || slug.startsWith('meta_')) {
    return PLATFORM_CHART_TOKENS.meta_ads;
  }

  // Google family → google_ads color.
  if (slug === 'google' || slug.startsWith('google')) {
    return PLATFORM_CHART_TOKENS.google_ads;
  }

  return PLATFORM_CHART_TOKENS.peer_avg;
}
