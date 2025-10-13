const STORAGE_NAMESPACE = "adinsights.table-view";

export const TABLE_VIEW_KEYS = {
  campaign: "campaign-performance",
  creative: "creative-performance",
} as const;

function isBrowserEnvironment(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function toStorageKey(id: string): string {
  return `${STORAGE_NAMESPACE}.${id}`;
}

export function loadSavedView<T = unknown>(id: string): T | undefined {
  if (!isBrowserEnvironment()) {
    return undefined;
  }

  const key = toStorageKey(id);

  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) {
      return undefined;
    }
    return JSON.parse(raw) as T;
  } catch (error) {
    window.localStorage.removeItem(key);
    return undefined;
  }
}

export function saveView<T = unknown>(id: string, view: T): void {
  if (!isBrowserEnvironment()) {
    return;
  }

  try {
    window.localStorage.setItem(toStorageKey(id), JSON.stringify(view));
  } catch (error) {
    // Swallow write errors to keep the tables functional even if storage is unavailable.
  }
}

export function clearView(id: string): void {
  if (!isBrowserEnvironment()) {
    return;
  }

  try {
    window.localStorage.removeItem(toStorageKey(id));
  } catch (error) {
    // Ignore failures triggered by storage restrictions.
  }
}

/**
 * Storage keys reserved for persisted table views:
 * - `adinsights.table-view.campaign-performance`
 * - `adinsights.table-view.creative-performance`
 */
