export type AuthUserRecord = Record<string, unknown> | undefined;

function normalizeRole(value: unknown): string | null {
  if (typeof value !== 'string') {
    return null;
  }
  const normalized = value.trim().toUpperCase();
  return normalized || null;
}

export function getUserRoles(user: AuthUserRecord): string[] {
  const rawRoles = user?.roles;
  if (!Array.isArray(rawRoles)) {
    return [];
  }

  const roles = rawRoles
    .map((role) => normalizeRole(role))
    .filter((role): role is string => Boolean(role));

  return Array.from(new Set(roles));
}

export function isViewerOnlyUser(user: AuthUserRecord): boolean {
  const roles = getUserRoles(user);
  return roles.length > 0 && roles.every((role) => role === 'VIEWER');
}

export function canAccessCreatorUi(user: AuthUserRecord): boolean {
  return !isViewerOnlyUser(user);
}
