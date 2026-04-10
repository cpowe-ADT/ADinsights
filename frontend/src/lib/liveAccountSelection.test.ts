import { beforeEach, describe, expect, it } from 'vitest';

import {
  buildLiveAccountOption,
  chooseDefaultLiveAccountOptionId,
  getLastLiveAccountId,
  setLastLiveAccountId,
  sortLiveAccountOptions,
  type LiveAccountOption,
} from './liveAccountSelection';

const STORAGE_KEY = 'adinsights.live-account-selection';

describe('liveAccountSelection', () => {
  const tenantId = 'tenant-1';

  beforeEach(() => {
    window.localStorage.clear();
  });

  // ── buildLiveAccountOption ────────────────────────────────────────

  describe('buildLiveAccountOption', () => {
    it('builds option from external_id and name', () => {
      const result = buildLiveAccountOption({
        external_id: 'act_123',
        account_id: '123',
        name: 'My Campaign',
      });
      expect(result).toEqual({ value: 'act_123', label: 'My Campaign · 123' });
    });

    it('falls back to account_id when external_id is missing', () => {
      const result = buildLiveAccountOption({
        account_id: '456',
        name: 'Test Account',
      });
      expect(result).toEqual({ value: '456', label: 'Test Account · 456' });
    });

    it('uses business_name when name is numeric', () => {
      const result = buildLiveAccountOption({
        external_id: 'act_789',
        account_id: '789',
        name: '789',
        business_name: 'Acme Corp',
      });
      expect(result).toEqual({ value: 'act_789', label: 'Acme Corp · 789' });
    });

    it('returns null when both external_id and account_id are missing', () => {
      expect(buildLiveAccountOption({})).toBeNull();
      expect(buildLiveAccountOption({ external_id: null, account_id: null })).toBeNull();
      expect(buildLiveAccountOption({ external_id: '', account_id: '' })).toBeNull();
    });

    it('returns null for whitespace-only ids', () => {
      expect(buildLiveAccountOption({ external_id: '  ', account_id: '  ' })).toBeNull();
    });

    it('uses raw name as label when name normalizes to match the account id', () => {
      const result = buildLiveAccountOption({
        external_id: 'act_100',
        account_id: '100',
        name: 'act_100',
      });
      // name 'act_100' normalizes to '100' which matches accountId, so no suffix appended
      expect(result).toEqual({ value: 'act_100', label: 'act_100' });
    });

    it('omits label suffix when primary label equals accountId', () => {
      const result = buildLiveAccountOption({
        external_id: 'act_555',
        account_id: '555',
        name: '555',
      });
      expect(result).toEqual({ value: 'act_555', label: '555' });
    });
  });

  // ── sortLiveAccountOptions ────────────────────────────────────────

  describe('sortLiveAccountOptions', () => {
    it('sorts named accounts before numeric-only labels', () => {
      const options: LiveAccountOption[] = [
        { value: 'act_111', label: '111' },
        { value: 'act_222', label: 'Zebra Corp · 222' },
        { value: 'act_333', label: 'Alpha Inc · 333' },
      ];
      const sorted = sortLiveAccountOptions(options);
      expect(sorted.map((o) => o.value)).toEqual(['act_333', 'act_222', 'act_111']);
    });

    it('alphabetizes within the same group', () => {
      const options: LiveAccountOption[] = [
        { value: 'b', label: 'Bravo' },
        { value: 'a', label: 'Alpha' },
        { value: 'c', label: 'Charlie' },
      ];
      const sorted = sortLiveAccountOptions(options);
      expect(sorted.map((o) => o.label)).toEqual(['Alpha', 'Bravo', 'Charlie']);
    });

    it('does not mutate the original array', () => {
      const options: LiveAccountOption[] = [
        { value: '2', label: '200' },
        { value: '1', label: 'Acme' },
      ];
      const original = [...options];
      sortLiveAccountOptions(options);
      expect(options).toEqual(original);
    });

    it('returns empty array for empty input', () => {
      expect(sortLiveAccountOptions([])).toEqual([]);
    });
  });

  // ── setLastLiveAccountId / getLastLiveAccountId ───────────────────

  describe('setLastLiveAccountId / getLastLiveAccountId', () => {
    it('stores and retrieves a per-tenant account id', () => {
      setLastLiveAccountId('tenant-a', 'act_100', 'user');
      expect(getLastLiveAccountId('tenant-a')).toBe('act_100');
    });

    it('isolates tenants from each other', () => {
      setLastLiveAccountId('tenant-a', 'act_100', 'user');
      setLastLiveAccountId('tenant-b', 'act_200', 'user');
      expect(getLastLiveAccountId('tenant-a')).toBe('act_100');
      expect(getLastLiveAccountId('tenant-b')).toBe('act_200');
    });

    it('returns undefined for unknown tenant', () => {
      expect(getLastLiveAccountId('nonexistent')).toBeUndefined();
    });

    it('returns undefined when tenantId is undefined or empty', () => {
      expect(getLastLiveAccountId(undefined)).toBeUndefined();
      expect(getLastLiveAccountId('')).toBeUndefined();
      expect(getLastLiveAccountId('  ')).toBeUndefined();
    });

    it('no-ops when tenantId is empty', () => {
      setLastLiveAccountId('', 'act_100', 'user');
      expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull();
    });

    it('no-ops when accountId is empty', () => {
      setLastLiveAccountId('tenant-a', '', 'user');
      expect(getLastLiveAccountId('tenant-a')).toBeUndefined();
    });

    it('defaults source to user', () => {
      setLastLiveAccountId('tenant-a', 'act_100');
      const raw = JSON.parse(window.localStorage.getItem(STORAGE_KEY)!);
      expect(raw['tenant-a']).toEqual({ accountId: 'act_100', source: 'user' });
    });

    it('overwrites previous selection for the same tenant', () => {
      setLastLiveAccountId('tenant-a', 'act_100', 'user');
      setLastLiveAccountId('tenant-a', 'act_200', 'auto');
      expect(getLastLiveAccountId('tenant-a')).toBe('act_200');
    });

    it('reads legacy string format from localStorage', () => {
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ 'tenant-x': 'act_legacy' }),
      );
      expect(getLastLiveAccountId('tenant-x')).toBe('act_legacy');
    });

    it('handles corrupted localStorage gracefully', () => {
      window.localStorage.setItem(STORAGE_KEY, 'not-valid-json{{{');
      expect(getLastLiveAccountId('tenant-a')).toBeUndefined();
    });

    it('skips write when value is identical', () => {
      setLastLiveAccountId('tenant-a', 'act_100', 'user');
      const afterFirst = window.localStorage.getItem(STORAGE_KEY);
      // Spy on setItem to confirm no redundant write
      const spy = vi.spyOn(Storage.prototype, 'setItem');
      setLastLiveAccountId('tenant-a', 'act_100', 'user');
      expect(spy).not.toHaveBeenCalled();
      spy.mockRestore();
    });
  });

  // ── chooseDefaultLiveAccountOptionId ──────────────────────────────

  describe('chooseDefaultLiveAccountOptionId', () => {
    const options: LiveAccountOption[] = sortLiveAccountOptions([
      { value: 'act_335732240', label: 'Adtelligent · 335732240' },
      { value: 'act_697812007883214', label: 'JDIC Adtelligent Ad Account · 697812007883214' },
      { value: 'act_791712443035541', label: "Students' Loan Bureau (SLB) · 791712443035541" },
    ]);

    it('returns undefined for empty options', () => {
      expect(chooseDefaultLiveAccountOptionId([], tenantId)).toBeUndefined();
    });

    it('returns stored user selection when valid', () => {
      setLastLiveAccountId(tenantId, 'act_791712443035541', 'user');
      expect(
        chooseDefaultLiveAccountOptionId(options, tenantId, ['act_697812007883214']),
      ).toBe('act_791712443035541');
    });

    it('prefers the credential account over a legacy first-option selection', () => {
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ [tenantId]: 'act_335732240' }),
      );

      expect(
        chooseDefaultLiveAccountOptionId(options, tenantId, ['act_697812007883214']),
      ).toBe('act_697812007883214');
    });

    it('preserves a legacy stored selection when it is not the fallback first option', () => {
      window.localStorage.setItem(
        STORAGE_KEY,
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

    it('returns preferred account when no stored selection exists', () => {
      expect(
        chooseDefaultLiveAccountOptionId(options, tenantId, ['act_791712443035541']),
      ).toBe('act_791712443035541');
    });

    it('returns first option as fallback when no stored or preferred', () => {
      const result = chooseDefaultLiveAccountOptionId(options, tenantId, []);
      // Should be the first in sorted order
      expect(options.map((o) => o.value)).toContain(result);
      expect(result).toBe(options[0].value);
    });

    it('ignores stored selection that is no longer in options', () => {
      setLastLiveAccountId(tenantId, 'act_deleted_999', 'user');
      const result = chooseDefaultLiveAccountOptionId(options, tenantId);
      expect(result).toBe(options[0].value);
    });

    it('works without tenantId (no stored selection)', () => {
      const result = chooseDefaultLiveAccountOptionId(options, undefined, [
        'act_697812007883214',
      ]);
      expect(result).toBe('act_697812007883214');
    });
  });
});
