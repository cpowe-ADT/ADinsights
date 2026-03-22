import { describe, expect, it } from 'vitest';

import { canAccessCreatorUi, getUserRoles, isViewerOnlyUser } from './rbac';

describe('rbac helpers', () => {
  it('normalizes and de-duplicates user roles', () => {
    expect(
      getUserRoles({
        roles: ['viewer', ' VIEWER ', 'analyst', null],
      }),
    ).toEqual(['VIEWER', 'ANALYST']);
  });

  it('detects viewer-only users', () => {
    expect(isViewerOnlyUser({ roles: ['viewer'] })).toBe(true);
    expect(isViewerOnlyUser({ roles: ['viewer', 'VIEWER'] })).toBe(true);
    expect(isViewerOnlyUser({ roles: ['viewer', 'analyst'] })).toBe(false);
    expect(isViewerOnlyUser(undefined)).toBe(false);
  });

  it('allows creator ui when roles are missing or elevated', () => {
    expect(canAccessCreatorUi(undefined)).toBe(true);
    expect(canAccessCreatorUi({ roles: ['admin'] })).toBe(true);
    expect(canAccessCreatorUi({ roles: ['analyst'] })).toBe(true);
    expect(canAccessCreatorUi({ roles: ['viewer'] })).toBe(false);
  });
});
