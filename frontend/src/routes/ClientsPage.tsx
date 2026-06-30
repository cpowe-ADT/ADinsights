import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import DashboardState from '../components/DashboardState';
import SkeletonLoader from '../components/SkeletonLoader';
import {
  createClient,
  listClients,
  PLATFORM_KEYS,
  platformLabel,
  totalAccountCount,
  type ClientSummary,
  type PlatformKey,
} from '../lib/clients';
import { formatAbsoluteTime, formatRelativeTime } from '../lib/format';
import { canAccessCreatorUi } from '../lib/rbac';
import '../styles/phase2.css';
import '../styles/dashboard.css';
import '../styles/skeleton.css';

const ClientsPage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const canCreate = canAccessCreatorUi(user);
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [clients, setClients] = useState<ClientSummary[]>([]);
  const [error, setError] = useState('Unable to load clients.');
  const [search, setSearch] = useState('');
  const [onlyActive, setOnlyActive] = useState(true);
  const [creating, setCreating] = useState(false);
  const [createName, setCreateName] = useState('');
  const [createError, setCreateError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setState('loading');
    try {
      const data = await listClients({
        search: search.trim() || undefined,
        active: onlyActive || undefined,
        page_size: 100,
      });
      setClients(data.results ?? []);
      setState('ready');
    } catch (err) {
      setState('error');
      setError(err instanceof Error ? err.message : 'Unable to load clients.');
    }
  }, [search, onlyActive]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleCreate = useCallback(async () => {
    const trimmed = createName.trim();
    if (!trimmed) {
      setCreateError('Name is required.');
      return;
    }
    setCreating(true);
    setCreateError(null);
    try {
      const created = await createClient({ name: trimmed });
      setCreateName('');
      navigate(`/clients/${created.id}`);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Unable to create client.');
    } finally {
      setCreating(false);
    }
  }, [createName, navigate]);

  const visiblePlatforms = useMemo<PlatformKey[]>(
    () => ['google_ads', 'meta_ads', 'meta_page'],
    [],
  );

  if (state === 'loading') {
    return (
      <section className="phase2-page">
        <header className="phase2-page__header">
          <div>
            <p className="dashboardEyebrow">Clients</p>
            <h1 className="dashboardHeading">Client Groups</h1>
          </div>
        </header>
        <SkeletonLoader variant="table" />
      </section>
    );
  }

  if (state === 'error') {
    return (
      <DashboardState
        variant="error"
        layout="page"
        title="Clients unavailable"
        message={error}
        actionLabel="Retry"
        onAction={() => void load()}
      />
    );
  }

  return (
    <section className="phase2-page">
      <header className="phase2-page__header">
        <div>
          <p className="dashboardEyebrow">Clients</p>
          <h1 className="dashboardHeading">Client Groups</h1>
          <p className="phase2-page__subhead">
            Link Meta ad accounts, Google Ads customers, and Meta Pages to a single client for
            cross-platform dashboards.
          </p>
        </div>
        <div className="phase2-row-actions">
          <Link to="/clients/suggest" className="button tertiary">
            Suggested groups
          </Link>
          <button type="button" className="button secondary" onClick={() => void load()}>
            Refresh
          </button>
        </div>
      </header>

      <div className="phase2-filter-bar">
        <label className="phase2-filter">
          <span>Search</span>
          <input
            type="search"
            placeholder="Name or slug"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <label className="phase2-filter">
          <input
            type="checkbox"
            checked={onlyActive}
            onChange={(event) => setOnlyActive(event.target.checked)}
          />
          <span>Active only</span>
        </label>
      </div>

      {canCreate ? (
        <div className="phase2-card" role="group" aria-label="Create client">
          <div className="phase2-card__header">
            <h2>Create client</h2>
          </div>
          <div className="phase2-card__body phase2-row">
            <input
              type="text"
              className="phase2-input"
              placeholder="Client name (e.g. JDIC)"
              value={createName}
              onChange={(event) => setCreateName(event.target.value)}
              disabled={creating}
            />
            <button
              type="button"
              className="button primary"
              onClick={() => void handleCreate()}
              disabled={creating || !createName.trim()}
            >
              {creating ? 'Creating…' : 'Create'}
            </button>
          </div>
          {createError ? (
            <p className="phase2-card__error" role="alert">
              {createError}
            </p>
          ) : null}
        </div>
      ) : null}

      {clients.length === 0 ? (
        <DashboardState
          variant="empty"
          layout="panel"
          title="No clients yet"
          message={
            canCreate
              ? 'Create one above or review suggested groups derived from your connected accounts.'
              : 'Ask an administrator to create and attach client groups.'
          }
        />
      ) : (
        <table className="phase2-table" aria-label="Clients">
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">Parish</th>
              <th scope="col">Industry</th>
              {visiblePlatforms.map((platform) => (
                <th scope="col" key={platform}>
                  {platformLabel(platform)}
                </th>
              ))}
              <th scope="col">Total accounts</th>
              <th scope="col">Updated</th>
            </tr>
          </thead>
          <tbody>
            {clients.map((client) => (
              <tr
                key={client.id}
                onClick={() => navigate(`/clients/${client.id}`)}
                className="phase2-table__row--clickable"
              >
                <td>
                  <Link to={`/clients/${client.id}`} className="phase2-link">
                    {client.name}
                  </Link>
                  {!client.is_active ? (
                    <span className="phase2-badge phase2-badge--muted">Inactive</span>
                  ) : null}
                </td>
                <td>{client.parish ?? '—'}</td>
                <td>{client.industry ?? '—'}</td>
                {visiblePlatforms.map((platform) => (
                  <td key={platform}>{client.platform_counts?.[platform] ?? 0}</td>
                ))}
                <td>
                  <strong>{totalAccountCount(client)}</strong>
                </td>
                <td title={formatAbsoluteTime(client.updated_at) ?? undefined}>
                  {formatRelativeTime(client.updated_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <p className="phase2-footnote">
        Platforms reserved for future sprints (not shown in the grid):{' '}
        {PLATFORM_KEYS.filter((p) => !visiblePlatforms.includes(p))
          .map(platformLabel)
          .join(', ')}
        .
      </p>
    </section>
  );
};

export default ClientsPage;
