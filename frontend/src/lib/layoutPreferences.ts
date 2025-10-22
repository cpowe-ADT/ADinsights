import type { MetricKey } from '../state/useDashboardStore';

export interface DashboardLayoutPreferences {
  metric: MetricKey;
  parish?: string;
}

const STORAGE_KEY = 'adinsights.dashboard-layout';

function isBrowser(): boolean {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';
}

export function loadDashboardLayout(): DashboardLayoutPreferences | undefined {
  if (!isBrowser()) {
    return undefined;
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return undefined;
    }

    const parsed = JSON.parse(raw) as Partial<DashboardLayoutPreferences> | null;
    if (!parsed || typeof parsed.metric !== 'string') {
      return undefined;
    }

    return {
      metric: parsed.metric as MetricKey,
      parish:
        typeof parsed.parish === 'string' && parsed.parish.trim().length > 0
          ? parsed.parish
          : undefined,
    };
  } catch {
    window.localStorage.removeItem(STORAGE_KEY);
    return undefined;
  }
}

export function saveDashboardLayout(preferences: DashboardLayoutPreferences): void {
  if (!isBrowser()) {
    return;
  }

  try {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ metric: preferences.metric, parish: preferences.parish ?? null }),
    );
  } catch {
    // Silently ignore write failures caused by storage quotas or privacy modes.
  }
}
