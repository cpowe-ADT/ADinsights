/**
 * Saved report layouts API client — tenant/owner-scoped persistence for the
 * report builder, backed by `SavedReportLayoutViewSet`
 * (`/api/analytics/report-layouts/`). The `config` field round-trips a
 * {@link DashboardLayoutConfig} verbatim.
 *
 * Callers should treat the network as best-effort and fall back to
 * {@link ./layoutStorage} (localStorage) when offline or unauthenticated — see
 * {@link ReportLayoutPreview}.
 */
import { del, get, patch, post } from '../../lib/apiClient';

import { isDashboardLayoutConfig, type DashboardLayoutConfig } from './layoutSchema';

const BASE = '/analytics/report-layouts/';

/** A persisted layout row as returned by the API. */
export interface SavedReportLayout {
  id: string;
  name: string;
  description: string;
  config: DashboardLayoutConfig;
  is_shared: boolean;
  created_at: string;
  updated_at: string;
}

/** Fields a client may write. `config` carries the grid definition. */
export interface SavedReportLayoutInput {
  name: string;
  config: DashboardLayoutConfig;
  description?: string;
  is_shared?: boolean;
}

/** DRF list responses may be paginated (`{results}`) or a bare array. */
interface Paginated<T> {
  results: T[];
}

const unwrapList = <T,>(payload: T[] | Paginated<T>): T[] =>
  Array.isArray(payload) ? payload : (payload?.results ?? []);

/** List layouts visible to the current user (own + shared, newest first). */
export const listSavedLayouts = async (
  options?: { signal?: AbortSignal },
): Promise<SavedReportLayout[]> => {
  const payload = await get<SavedReportLayout[] | Paginated<SavedReportLayout>>(BASE, options);
  return unwrapList(payload);
};

/** Fetch a single layout by id. */
export const getSavedLayout = (
  id: string,
  options?: { signal?: AbortSignal },
): Promise<SavedReportLayout> =>
  get<SavedReportLayout>(`${BASE}${encodeURIComponent(id)}/`, options);

/** Create a new saved layout. The server stamps tenant + owner. */
export const createSavedLayout = (
  input: SavedReportLayoutInput,
): Promise<SavedReportLayout> => post<SavedReportLayout>(BASE, input);

/** Patch an existing layout (partial update). */
export const updateSavedLayout = (
  id: string,
  input: Partial<SavedReportLayoutInput>,
): Promise<SavedReportLayout> =>
  patch<SavedReportLayout>(`${BASE}${encodeURIComponent(id)}/`, input);

/** Delete a layout by id. */
export const deleteSavedLayout = (id: string): Promise<void> =>
  del<void>(`${BASE}${encodeURIComponent(id)}/`);

/**
 * Upsert helper: create when `id` is absent, otherwise patch. Validates the
 * config shape before sending so we never persist a malformed layout.
 */
export const saveLayoutToApi = (
  layout: DashboardLayoutConfig,
  meta: { id?: string; name?: string; is_shared?: boolean },
): Promise<SavedReportLayout> => {
  if (!isDashboardLayoutConfig(layout)) {
    return Promise.reject(new Error('Invalid layout config'));
  }
  const input: SavedReportLayoutInput = {
    name: meta.name ?? layout.title ?? layout.id,
    config: layout,
    is_shared: meta.is_shared,
  };
  return meta.id ? updateSavedLayout(meta.id, input) : createSavedLayout(input);
};
