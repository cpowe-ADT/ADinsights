export type DashboardSessionState = {
  activeTenantId?: string;
  activeTenantLabel?: string;
  resetVersion: number;
};

type DashboardSessionListener = (state: DashboardSessionState) => void;

let dashboardSessionState: DashboardSessionState = {
  activeTenantId: undefined,
  activeTenantLabel: undefined,
  resetVersion: 0,
};

const listeners = new Set<DashboardSessionListener>();

function normalizeTenantId(value?: string): string | undefined {
  if (typeof value !== 'string') {
    return undefined;
  }
  const normalized = value.trim();
  return normalized ? normalized : undefined;
}

function normalizeTenantLabel(value?: string): string | undefined {
  if (typeof value !== 'string') {
    return undefined;
  }
  const normalized = value.trim();
  return normalized ? normalized : undefined;
}

function emitDashboardSession(): void {
  const snapshot = getDashboardSessionState();
  listeners.forEach((listener) => listener(snapshot));
}

export function getDashboardSessionState(): DashboardSessionState {
  return { ...dashboardSessionState };
}

export function setDashboardSessionTenant(tenantId?: string, tenantLabel?: string): void {
  const nextTenantId = normalizeTenantId(tenantId);
  const nextTenantLabel = normalizeTenantLabel(tenantLabel);
  if (
    dashboardSessionState.activeTenantId === nextTenantId &&
    dashboardSessionState.activeTenantLabel === nextTenantLabel
  ) {
    return;
  }
  dashboardSessionState = {
    ...dashboardSessionState,
    activeTenantId: nextTenantId,
    activeTenantLabel: nextTenantLabel,
  };
  emitDashboardSession();
}

export function resetDashboardSession(): void {
  dashboardSessionState = {
    activeTenantId: undefined,
    activeTenantLabel: undefined,
    resetVersion: dashboardSessionState.resetVersion + 1,
  };
  emitDashboardSession();
}

export function subscribeDashboardSession(
  listener: DashboardSessionListener,
): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
