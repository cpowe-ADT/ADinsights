import { beforeEach, describe, expect, it } from 'vitest';

import {
  chooseDefaultLiveAccountOptionId,
  setLastLiveAccountId,
  sortLiveAccountOptions,
  type LiveAccountOption,
} from './liveAccountSelection';

describe('liveAccountSelection', () => {
  const tenantId = 'tenant-1';
  const options: LiveAccountOption[] = sortLiveAccountOptions([
    { value: 'act_335732240', label: 'Adtelligent · 335732240' },
    { value: 'act_697812007883214', label: 'JDIC Adtelligent Ad Account · 697812007883214' },
    { value: 'act_791712443035541', label: "Students' Loan Bureau (SLB) · 791712443035541" },
  ]);

  beforeEach(() => {
    window.localStorage.clear();
  });

  it('prefers the credential account over a legacy first-option selection', () => {
    window.localStorage.setItem(
      'adinsights.live-account-selection',
      JSON.stringify({ [tenantId]: 'act_335732240' }),
    );

    expect(
      chooseDefaultLiveAccountOptionId(options, tenantId, ['act_697812007883214']),
    ).toBe('act_697812007883214');
  });

  it('preserves a legacy stored selection when it is not the fallback first option', () => {
    window.localStorage.setItem(
      'adinsights.live-account-selection',
      JSON.stringify({ [tenantId]: 'act_791712443035541' }),
    );

    expect(
      chooseDefaultLiveAccountOptionId(options, tenantId, ['act_697812007883214']),
    ).toBe('act_791712443035541');
  });

  it('upgrades an auto-selected stored account to the credential account when available', () => {
    setLastLiveAccountId(tenantId, 'act_335732240', 'auto');

    expect(
      chooseDefaultLiveAccountOptionId(options, tenantId, ['act_697812007883214']),
    ).toBe('act_697812007883214');
  });

  it('respects an explicit user-selected account over the credential preference', () => {
    setLastLiveAccountId(tenantId, 'act_791712443035541', 'user');

    expect(
      chooseDefaultLiveAccountOptionId(options, tenantId, ['act_697812007883214']),
    ).toBe('act_791712443035541');
  });
});
