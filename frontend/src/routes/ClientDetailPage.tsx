import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import DashboardState from '../components/DashboardState';
import SkeletonLoader from '../components/SkeletonLoader';
import {
  attachClientAccount,
  deleteClient,
  detachClientAccount,
  getClient,
  PLATFORM_KEYS,
  platformLabel,
  updateClient,
  type AttachConflictPayload,
  type ClientDetail,
  type ClientPlatformAccountRecord,
  type PlatformKey,
} from '../lib/clients';
import { ApiError } from '../lib/apiClient';
import { formatAbsoluteTime, formatRelativeTime } from '../lib/format';
import { canAccessCreatorUi } from '../lib/rbac';
import '../styles/phase2.css';
import '../styles/dashboard.css';
import '../styles/skeleton.css';

const ATTACHABLE_PLATFORMS: PlatformKey[] = ['google_ads', 'meta_ads', 'meta_page'];

const ClientDetailPage = () => {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const navigate = useNavigate();
  const canEdit = canAccessCreatorUi(user);

  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [client, setClient] = useState<ClientDetail | null>(null);
  const [error, setError] = useState('Unable to load client.');

  // Attach form state
  const [attachPlatform, setAttachPlatform] = useState<PlatformKey>('meta_ads');
  const [attachExternalId, setAttachExternalId] = useState('');
  const [attachDisplayName, setAttachDisplayName] = useState('');
  const [attachPrimary, setAttachPrimary] = useState(false);
  const [attaching, setAttaching] = useState(false);
  const [attachError, setAttachError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setState('loading');
    try {
      const data = await getClient(id);
      setClient(data);
      setState('ready');
    } catch (err) {
      setState('error');
      setError(err instanceof Error ? err.message : 'Unable to load client.');
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleAttach = useCallback(async () => {
    if (!id) return;
    const trimmedExt = attachExternalId.trim();
    if (!trimmedExt) {
      setAttachError('External id is required.');
      return;
    }
    setAttaching(true);
    setAttachError(null);
    try {
      await attachClientAccount(id, {
        platform: attachPlatform,
        external_id: trimmedExt,
        display_name: attachDisplayName.trim() || undefined,
        is_primary: attachPrimary,
      });
      setAttachExternalId('');
      setAttachDisplayName('');
      setAttachPrimary(false);
      await load();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        const payload = err.payload as AttachConflictPayload | undefined;
        const claimedBy = payload?.claimed_by?.client_name;
        setAttachError(
          claimedBy
            ? `Already attached to “${claimedBy}”. Detach from that client first.`
            : 'Already attached to another client.',
        );
      } else {
        setAttachError(
          err instanceof Error ? err.message : 'Unable to attach account.',
        );
      }
    } finally {
      setAttaching(false);
    }
  }, [attachDisplayName, attachExternalId, attachPlatform, attachPrimary, id, load]);

  const handleDetach = useCallback(
    async (account: ClientPlatformAccountRecord) => {
      if (!id) return;
      if (
        !window.confirm(
          `Detach ${platformLabel(account.platform)} account ${account.external_id}?`,
        )
      ) {
        return;
      }
      try {
        await detachClientAccount(id, account.id);
        await load();
      } catch (err) {
        setAttachError(
          err instanceof Error ? err.message : 'Unable to detach account.',
        );
      }
    },
    [id, load],
  );

  const handleToggleActive = useCallback(async () => {
    if (!id || !client) return;
    try {
      const updated = await updateClient(id, { is_active: !client.is_active });
      setClient(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to update client.');
    }
  }, [client, id]);

  const handleDelete = useCallback(async () => {
    if (!id || !client) return;
    if (
      !window.confirm(
        `Delete client “${client.name}”? All platform attachments will be removed. This cannot be undone.`,
      )
    ) {
      return;
    }
    try {
      await deleteClient(id);
      navigate('/clients');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to delete client.');
    }
  }, [client, id, navigate]);

  if (state === 'loading') {
    return (
      <section className="phase2-page">
        <SkeletonLoader variant="card" />
      </section>
    );
  }

  if (state === 'error' || !client) {
    return (
      <DashboardState
        variant="error"
        layout="page"
        title="Client unavailable"
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
          <p className="dashboardEyebrow">
            <Link to="/clients" className="phase2-link">
              ← Clients
            </Link>
          </p>
          <h1 className="dashboardHeading">{client.name}</h1>
          <p className="phase2-page__subhead">
            {client.is_active ? 'Active' : 'Inactive'} · slug{' '}
            <code>{client.slug}</code> · updated{' '}
            <span title={formatAbsoluteTime(client.updated_at) ?? undefined}>
              {formatRelativeTime(client.updated_at)}
            </span>
          </p>
        </div>
        <div className="phase2-row-actions">
          <Link to={`/dashboards?client_id=${client.id}`} className="button primary">
            Open dashboards
          </Link>
          {canEdit ? (
            <>
              <button
                type="button"
                className="button tertiary"
                onClick={() => void handleToggleActive()}
              >
                {client.is_active ? 'Deactivate' : 'Activate'}
              </button>
              <button
                type="button"
                className="button danger"
                onClick={() => void handleDelete()}
              >
                Delete
              </button>
            </>
          ) : null}
        </div>
      </header>

      <div className="phase2-card" aria-label="Platform accounts">
        <div className="phase2-card__header">
          <h2>Linked accounts ({client.platform_accounts.length})</h2>
        </div>
        <div className="phase2-card__body">
          {client.platform_accounts.length === 0 ? (
            <p className="phase2-empty">No accounts attached yet.</p>
          ) : (
            <table className="phase2-table" aria-label="Linked platform accounts">
              <thead>
                <tr>
                  <th scope="col">Platform</th>
                  <th scope="col">External ID</th>
                  <th scope="col">Display</th>
                  <th scope="col">Primary</th>
                  <th scope="col">Attached</th>
                  {canEdit ? <th scope="col" aria-label="Actions" /> : null}
                </tr>
              </thead>
              <tbody>
                {client.platform_accounts.map((account) => (
                  <tr key={account.id}>
                    <td>
                      <span className="phase2-badge">
                        {platformLabel(account.platform)}
                      </span>
                    </td>
                    <td>
                      <code>{account.external_id}</code>
                    </td>
                    <td>{account.display_name ?? '—'}</td>
                    <td>{account.is_primary ? 'Yes' : ''}</td>
                    <td title={formatAbsoluteTime(account.created_at) ?? undefined}>
                      {formatRelativeTime(account.created_at)}
                    </td>
                    {canEdit ? (
                      <td>
                        <button
                          type="button"
                          className="button tertiary"
                          onClick={() => void handleDetach(account)}
                        >
                          Detach
                        </button>
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {canEdit ? (
        <div className="phase2-card" aria-label="Attach account">
          <div className="phase2-card__header">
            <h2>Attach account</h2>
          </div>
          <div className="phase2-card__body phase2-row phase2-row--wrap">
            <label className="phase2-filter">
              <span>Platform</span>
              <select
                value={attachPlatform}
                onChange={(event) =>
                  setAttachPlatform(event.target.value as PlatformKey)
                }
              >
                {ATTACHABLE_PLATFORMS.map((p) => (
                  <option key={p} value={p}>
                    {platformLabel(p)}
                  </option>
                ))}
              </select>
            </label>
            <label className="phase2-filter">
              <span>External ID</span>
              <input
                type="text"
                placeholder={
                  attachPlatform === 'meta_ads'
                    ? 'act_123456789'
                    : attachPlatform === 'google_ads'
                      ? '1234567890'
                      : 'Page ID'
                }
                value={attachExternalId}
                onChange={(event) => setAttachExternalId(event.target.value)}
                disabled={attaching}
              />
            </label>
            <label className="phase2-filter">
              <span>Display name (optional)</span>
              <input
                type="text"
                value={attachDisplayName}
                onChange={(event) => setAttachDisplayName(event.target.value)}
                disabled={attaching}
              />
            </label>
            <label className="phase2-filter">
              <input
                type="checkbox"
                checked={attachPrimary}
                onChange={(event) => setAttachPrimary(event.target.checked)}
                disabled={attaching}
              />
              <span>Primary for this platform</span>
            </label>
            <button
              type="button"
              className="button primary"
              onClick={() => void handleAttach()}
              disabled={attaching || !attachExternalId.trim()}
            >
              {attaching ? 'Attaching…' : 'Attach'}
            </button>
          </div>
          {attachError ? (
            <p className="phase2-card__error" role="alert">
              {attachError}
            </p>
          ) : null}
          <p className="phase2-card__hint">
            Only {ATTACHABLE_PLATFORMS.map(platformLabel).join(', ')} are wired up
            today. Other platforms ({PLATFORM_KEYS.filter(
              (p) => !ATTACHABLE_PLATFORMS.includes(p),
            ).map(platformLabel).join(', ')}) will be enabled in future sprints.
          </p>
        </div>
      ) : null}
    </section>
  );
};

export default ClientDetailPage;
