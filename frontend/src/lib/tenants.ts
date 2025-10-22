import { fetchTenants, type TenantRecord } from './dataService';

export interface TenantOption {
  id: string;
  name: string;
  slug?: string;
  status?: string;
}

const TENANTS_ENDPOINT = '/tenants/';
const TENANTS_FIXTURE_PATH = '/mock/tenants.json';

function normalizeTenantId(value: TenantRecord['id']): string {
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (trimmed) {
      return trimmed;
    }
  }

  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(value);
  }

  throw new Error('Tenant is missing an identifier');
}

function normalizeTenantName(value: TenantRecord['name']): string {
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (trimmed) {
      return trimmed;
    }
  }

  throw new Error('Tenant is missing a name');
}

function normalizeTenant(record: TenantRecord): TenantOption {
  const id = normalizeTenantId(record.id);
  const name = normalizeTenantName(record.name);
  const slug =
    typeof record.slug === 'string' && record.slug.trim() ? record.slug.trim() : undefined;
  const status =
    typeof record.status === 'string' && record.status.trim() ? record.status.trim() : undefined;

  return {
    id,
    name,
    slug,
    status,
  };
}

export async function loadTenants(signal?: AbortSignal): Promise<TenantOption[]> {
  const records = await fetchTenants({
    path: TENANTS_ENDPOINT,
    mockPath: TENANTS_FIXTURE_PATH,
    signal,
  });

  const seen = new Set<string>();
  const tenants = records
    .map((record) => {
      try {
        return normalizeTenant(record);
      } catch (error) {
        console.warn('Skipping invalid tenant record', error, record);
        return undefined;
      }
    })
    .filter((tenant): tenant is TenantOption => Boolean(tenant))
    .filter((tenant) => {
      if (seen.has(tenant.id)) {
        return false;
      }
      seen.add(tenant.id);
      return true;
    })
    .sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }));

  return tenants;
}
