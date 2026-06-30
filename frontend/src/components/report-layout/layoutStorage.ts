/**
 * Layout persistence. localStorage today (per-browser, instant), so "Save"
 * actually works; a tenant/user-scoped backend store is the planned follow-up
 * (the schema serializes cleanly either way).
 */
import { isDashboardLayoutConfig, type DashboardLayoutConfig } from './layoutSchema';

const KEY_PREFIX = 'adinsights.report-layout.';

export function saveLayout(layout: DashboardLayoutConfig): void {
  try {
    window.localStorage.setItem(KEY_PREFIX + layout.id, JSON.stringify(layout));
  } catch {
    // Storage unavailable (private mode / quota) — saving is best-effort.
  }
}

export function loadLayout(id: string): DashboardLayoutConfig | null {
  try {
    const raw = window.localStorage.getItem(KEY_PREFIX + id);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    return isDashboardLayoutConfig(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function clearLayout(id: string): void {
  try {
    window.localStorage.removeItem(KEY_PREFIX + id);
  } catch {
    // ignore
  }
}
