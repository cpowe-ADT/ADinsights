const STORAGE_KEY = 'adinsights.live-account-selection';

type AccountSelectionSource = 'user' | 'auto' | 'legacy';
type PersistedAccountSelection = string | { accountId?: string; source?: string };
type AccountSelectionRecord = Record<
  string,
  {
    accountId: string;
    source: AccountSelectionSource;
  }
>;
type LiveAccountLike = {
  external_id?: string | null;
  account_id?: string | null;
  name?: string | null;
  business_name?: string | null;
};

export interface LiveAccountOption {
  value: string;
  label: string;
}

function primaryOptionLabel(label: string): string {
  return label.split(' · ')[0]?.trim() ?? '';
}

function isPlaceholderOption(option: LiveAccountOption): boolean {
  return isNumericLabel(primaryOptionLabel(option.label));
}

function normalizeText(value: string | null | undefined): string {
  return typeof value === 'string' ? value.trim() : '';
}

function isNumericLabel(value: string): boolean {
  return /^\d+$/.test(value);
}

function firstMatchingPreferredAccountId(
  validAccountIds: string[],
  preferredAccountIds: string[] = [],
): string | undefined {
  for (const candidate of preferredAccountIds.map((value) => value.trim()).filter(Boolean)) {
    if (validAccountIds.includes(candidate)) {
      return candidate;
    }
  }
  return undefined;
}

function normalizeAccountValue(value: string): string {
  return value.startsWith('act_') ? value.slice(4) : value;
}

function resolvePrimaryAccountLabel(account: LiveAccountLike, accountId: string): string {
  const name = normalizeText(account.name);
  if (name && !isNumericLabel(name) && normalizeAccountValue(name) !== normalizeAccountValue(accountId)) {
    return name;
  }

  const businessName = normalizeText(account.business_name);
  if (businessName) {
    return businessName;
  }

  if (name) {
    return name;
  }

  return accountId;
}

export function buildLiveAccountOption(account: LiveAccountLike): LiveAccountOption | null {
  const value = normalizeText(account.external_id) || normalizeText(account.account_id);
  if (!value) {
    return null;
  }

  const accountId = normalizeText(account.account_id) || normalizeAccountValue(value);
  const primaryLabel = resolvePrimaryAccountLabel(account, accountId);

  return {
    value,
    label:
      primaryLabel && accountId && normalizeAccountValue(primaryLabel) !== normalizeAccountValue(accountId)
        ? `${primaryLabel} · ${accountId}`
        : primaryLabel || accountId,
  };
}

export function sortLiveAccountOptions(options: LiveAccountOption[]): LiveAccountOption[] {
  return [...options].sort((left, right) => {
    const leftPrimary = primaryOptionLabel(left.label);
    const rightPrimary = primaryOptionLabel(right.label);
    const leftRank = isNumericLabel(leftPrimary) ? 1 : 0;
    const rightRank = isNumericLabel(rightPrimary) ? 1 : 0;
    if (leftRank !== rightRank) {
      return leftRank - rightRank;
    }
    return left.label.localeCompare(right.label, undefined, { sensitivity: 'base' });
  });
}

function readSelections(): AccountSelectionRecord {
  if (typeof window === 'undefined' || !window.localStorage) {
    return {};
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return {};
    }
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== 'object') {
      return {};
    }
    return Object.entries(parsed as Record<string, unknown>).reduce<AccountSelectionRecord>(
      (acc, [tenantId, selection]) => {
        if (typeof selection === 'string' && selection.trim()) {
          acc[tenantId] = {
            accountId: selection.trim(),
            source: 'legacy',
          };
          return acc;
        }
        if (!selection || typeof selection !== 'object') {
          return acc;
        }
        const accountId =
          typeof (selection as PersistedAccountSelection & { accountId?: string }).accountId === 'string'
            ? (selection as PersistedAccountSelection & { accountId?: string }).accountId?.trim()
            : '';
        if (!accountId) {
          return acc;
        }
        const rawSource =
          typeof (selection as PersistedAccountSelection & { source?: string }).source === 'string'
            ? (selection as PersistedAccountSelection & { source?: string }).source?.trim().toLowerCase()
            : '';
        const source: AccountSelectionSource =
          rawSource === 'user' || rawSource === 'auto' ? (rawSource as AccountSelectionSource) : 'legacy';
        acc[tenantId] = { accountId, source };
        return acc;
      },
      {},
    );
  } catch {
    return {};
  }
}

function writeSelections(next: AccountSelectionRecord): void {
  if (typeof window === 'undefined' || !window.localStorage) {
    return;
  }
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Ignore local storage failures.
  }
}

export function getLastLiveAccountId(tenantId?: string): string | undefined {
  const normalizedTenantId = tenantId?.trim();
  if (!normalizedTenantId) {
    return undefined;
  }
  return readSelections()[normalizedTenantId]?.accountId;
}

function getLastLiveAccountSelection(
  tenantId?: string,
): { accountId: string; source: AccountSelectionSource } | undefined {
  const normalizedTenantId = tenantId?.trim();
  if (!normalizedTenantId) {
    return undefined;
  }
  return readSelections()[normalizedTenantId];
}

export function setLastLiveAccountId(
  tenantId: string | undefined,
  accountId: string,
  source: AccountSelectionSource = 'user',
): void {
  const normalizedTenantId = tenantId?.trim();
  const normalizedAccountId = accountId.trim();
  if (!normalizedTenantId || !normalizedAccountId) {
    return;
  }
  const current = readSelections();
  const existing = current[normalizedTenantId];
  if (existing?.accountId === normalizedAccountId && existing.source === source) {
    return;
  }
  writeSelections({
    ...current,
    [normalizedTenantId]: {
      accountId: normalizedAccountId,
      source,
    },
  });
}

export function chooseDefaultLiveAccountId(
  accountIds: string[],
  tenantId?: string,
  preferredAccountIds: string[] = [],
): string | undefined {
  const normalizedAccountIds = accountIds.map((value) => value.trim()).filter(Boolean);
  if (normalizedAccountIds.length === 0) {
    return undefined;
  }
  const stored = getLastLiveAccountSelection(tenantId);
  const preferred = firstMatchingPreferredAccountId(normalizedAccountIds, preferredAccountIds);
  if (stored && normalizedAccountIds.includes(stored.accountId)) {
    const firstAccountId = normalizedAccountIds[0];
    if (
      preferred &&
      preferred !== stored.accountId &&
      (stored.source === 'auto' || (stored.source === 'legacy' && stored.accountId === firstAccountId))
    ) {
      return preferred;
    }
    return stored.accountId;
  }

  if (preferred) {
    return preferred;
  }

  return normalizedAccountIds[0];
}

export function chooseDefaultLiveAccountOptionId(
  options: LiveAccountOption[],
  tenantId?: string,
  preferredAccountIds: string[] = [],
): string | undefined {
  const sortedOptions = sortLiveAccountOptions(options);
  if (sortedOptions.length === 0) {
    return undefined;
  }

  const validAccountIds = sortedOptions.map((option) => option.value.trim()).filter(Boolean);
  const stored = getLastLiveAccountSelection(tenantId);
  const preferred = firstMatchingPreferredAccountId(validAccountIds, preferredAccountIds);
  if (stored && validAccountIds.includes(stored.accountId)) {
    if (
      preferred &&
      preferred !== stored.accountId &&
      (stored.source === 'auto' ||
        (stored.source === 'legacy' && stored.accountId === validAccountIds[0]))
    ) {
      return preferred;
    }
    return stored.accountId;
  }

  if (preferred) {
    return preferred;
  }

  return validAccountIds[0];
}
