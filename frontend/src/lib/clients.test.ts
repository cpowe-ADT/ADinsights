import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  del: vi.fn(),
}));

vi.mock('./apiClient', () => ({
  __esModule: true,
  get: apiMock.get,
  post: apiMock.post,
  patch: apiMock.patch,
  del: apiMock.del,
  appendQueryParams: (path: string, params: Record<string, unknown>) => {
    const entries = Object.entries(params ?? {}).filter(
      ([, v]) => v !== undefined && v !== null && v !== '',
    );
    if (entries.length === 0) return path;
    const qs = entries.map(([k, v]) => `${k}=${v}`).join('&');
    return `${path}?${qs}`;
  },
}));

import {
  acknowledgeClientSuggestionSnapshot,
  applySuggestion,
  attachClientAccount,
  createClient,
  deleteClient,
  detachClientAccount,
  getClient,
  getClientSuggestionSnapshot,
  listClientAccounts,
  listClients,
  platformLabel,
  refreshClientSuggestionSnapshot,
  suggestClients,
  totalAccountCount,
  updateClient,
  type ClientSummary,
} from './clients';

describe('clients API client', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('listClients', () => {
    it('calls GET /clients/ with serialized filters', async () => {
      apiMock.get.mockResolvedValue({ count: 0, results: [] });
      await listClients({ search: 'bank', active: true, page_size: 50 });
      expect(apiMock.get).toHaveBeenCalledWith('/clients/?search=bank&active=true&page_size=50');
    });

    it('omits empty query params', async () => {
      apiMock.get.mockResolvedValue({ count: 0, results: [] });
      await listClients();
      expect(apiMock.get).toHaveBeenCalledWith('/clients/');
    });
  });

  describe('getClient / createClient / updateClient / deleteClient', () => {
    it('getClient GETs the detail path', async () => {
      apiMock.get.mockResolvedValue({ id: 'c1' });
      await getClient('c1');
      expect(apiMock.get).toHaveBeenCalledWith('/clients/c1/');
    });

    it('createClient POSTs to /clients/ with body', async () => {
      apiMock.post.mockResolvedValue({ id: 'c1', name: 'BOJ' });
      const result = await createClient({ name: 'BOJ' });
      expect(apiMock.post).toHaveBeenCalledWith('/clients/', { name: 'BOJ' });
      expect(result.name).toBe('BOJ');
    });

    it('updateClient PATCHes the detail path', async () => {
      apiMock.patch.mockResolvedValue({ id: 'c1', is_active: false });
      await updateClient('c1', { is_active: false });
      expect(apiMock.patch).toHaveBeenCalledWith('/clients/c1/', {
        is_active: false,
      });
    });

    it('deleteClient DELETEs the detail path', async () => {
      apiMock.del.mockResolvedValue(undefined);
      await deleteClient('c1');
      expect(apiMock.del).toHaveBeenCalledWith('/clients/c1/');
    });
  });

  describe('accounts', () => {
    it('listClientAccounts unwraps bare array', async () => {
      apiMock.get.mockResolvedValue([{ id: 'a1', platform: 'meta_ads' }]);
      const result = await listClientAccounts('c1');
      expect(apiMock.get).toHaveBeenCalledWith('/clients/c1/accounts/');
      expect(result).toHaveLength(1);
    });

    it('listClientAccounts unwraps paginated envelope', async () => {
      apiMock.get.mockResolvedValue({
        results: [{ id: 'a1', platform: 'google_ads' }],
      });
      const result = await listClientAccounts('c1');
      expect(result[0].platform).toBe('google_ads');
    });

    it('attachClientAccount POSTs to /clients/<id>/accounts/', async () => {
      apiMock.post.mockResolvedValue({ id: 'a1' });
      await attachClientAccount('c1', {
        platform: 'meta_ads',
        external_id: 'act_123',
        is_primary: true,
      });
      expect(apiMock.post).toHaveBeenCalledWith('/clients/c1/accounts/', {
        platform: 'meta_ads',
        external_id: 'act_123',
        is_primary: true,
      });
    });

    it('detachClientAccount DELETEs nested path', async () => {
      apiMock.del.mockResolvedValue(undefined);
      await detachClientAccount('c1', 'a1');
      expect(apiMock.del).toHaveBeenCalledWith('/clients/c1/accounts/a1/');
    });
  });

  describe('suggest', () => {
    it('suggestClients passes threshold', async () => {
      apiMock.get.mockResolvedValue({ threshold: 0.8, groups: [] });
      await suggestClients({ threshold: 0.8 });
      expect(apiMock.get).toHaveBeenCalledWith('/clients/suggest/?threshold=0.8');
    });

    it('applySuggestion POSTs to /clients/suggest/apply/', async () => {
      apiMock.post.mockResolvedValue({
        client_id: 'c1',
        attached: 2,
        client: { id: 'c1' },
      });
      await applySuggestion({
        create_name: 'JDIC',
        accounts: [
          { platform: 'meta_ads', external_id: 'act_1' },
          { platform: 'google_ads', external_id: '1234567890' },
        ],
      });
      expect(apiMock.post).toHaveBeenCalledWith('/clients/suggest/apply/', {
        create_name: 'JDIC',
        accounts: [
          { platform: 'meta_ads', external_id: 'act_1' },
          { platform: 'google_ads', external_id: '1234567890' },
        ],
      });
    });
  });

  describe('helpers', () => {
    it('platformLabel renders known platforms', () => {
      expect(platformLabel('meta_ads')).toBe('Meta Ads');
      expect(platformLabel('meta_page')).toBe('Meta Page');
      expect(platformLabel('google_ads')).toBe('Google Ads');
      expect(platformLabel('ga4')).toBe('GA4');
      expect(platformLabel('search_console')).toBe('Search Console');
      expect(platformLabel('linkedin')).toBe('LinkedIn');
      expect(platformLabel('tiktok')).toBe('TikTok');
    });

    it('totalAccountCount sums platform_counts values', () => {
      const summary: ClientSummary = {
        id: 'c1',
        name: 'BOJ',
        slug: 'boj',
        is_active: true,
        platform_counts: { meta_ads: 2, google_ads: 1, meta_page: 1 },
        updated_at: '2026-04-13',
      };
      expect(totalAccountCount(summary)).toBe(4);
    });

    it('totalAccountCount handles missing platform_counts', () => {
      const summary = {
        id: 'c1',
        name: 'BOJ',
        slug: 'boj',
        is_active: true,
        platform_counts: {},
        updated_at: '2026-04-13',
      } as ClientSummary;
      expect(totalAccountCount(summary)).toBe(0);
    });
  });

  describe('suggestion snapshot', () => {
    it('getClientSuggestionSnapshot GETs /clients/suggestions/latest/', async () => {
      apiMock.get.mockResolvedValue({ snapshot: null });
      const result = await getClientSuggestionSnapshot();
      expect(apiMock.get).toHaveBeenCalledWith('/clients/suggestions/latest/');
      expect(result).toEqual({ snapshot: null });
    });

    it('acknowledgeClientSuggestionSnapshot POSTs empty body', async () => {
      apiMock.post.mockResolvedValue({
        snapshot: { id: 's1', suggestion_count: 1 },
      });
      await acknowledgeClientSuggestionSnapshot();
      expect(apiMock.post).toHaveBeenCalledWith('/clients/suggestions/latest/acknowledge/', {});
    });

    it('refreshClientSuggestionSnapshot forwards threshold', async () => {
      apiMock.post.mockResolvedValue({ status: 'enqueued', threshold: 0.6 });
      await refreshClientSuggestionSnapshot(0.6);
      expect(apiMock.post).toHaveBeenCalledWith('/clients/suggestions/latest/refresh/', {
        threshold: 0.6,
      });
    });

    it('refreshClientSuggestionSnapshot sends empty body when threshold omitted', async () => {
      apiMock.post.mockResolvedValue({ status: 'enqueued', threshold: 0.7 });
      await refreshClientSuggestionSnapshot();
      expect(apiMock.post).toHaveBeenCalledWith('/clients/suggestions/latest/refresh/', {});
    });
  });
});
