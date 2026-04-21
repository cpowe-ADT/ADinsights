import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import DashboardState from '../components/DashboardState';
import SkeletonLoader from '../components/SkeletonLoader';
import {
  applySuggestion,
  platformLabel,
  suggestClients,
  type AttachRequest,
  type SuggestedGroup,
  type SuggestResponse,
} from '../lib/clients';
import { canAccessCreatorUi } from '../lib/rbac';
import '../styles/phase2.css';
import '../styles/dashboard.css';
import '../styles/skeleton.css';

/**
 * Sprint 7 of Client grouping: suggested groups page.
 *
 * Lists name-matched candidate groups from `/api/clients/suggest/` and lets a
 * creator apply a group in one click — either attaching all accounts to an
 * existing Client or creating a new one. Low-confidence accounts are shown
 * but unchecked by default; users can opt them back in before applying.
 */

// Confidence threshold below which we suggest but don't pre-check the row.
const SOFT_CONFIDENCE_CUTOFF = 0.75;

const ClientSuggestPage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const canApply = canAccessCreatorUi(user);

  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [response, setResponse] = useState<SuggestResponse | null>(null);
  const [error, setError] = useState('Unable to load suggestions.');
  const [threshold, setThreshold] = useState(0.7);

  // Per-group UI state. Keyed by SuggestedGroup.group_id to survive refresh.
  const [selectedAccounts, setSelectedAccounts] = useState<
    Record<string, Record<string, boolean>>
  >({});
  const [overrideName, setOverrideName] = useState<Record<string, string>>({});
  const [applying, setApplying] = useState<Record<string, boolean>>({});
  const [applyError, setApplyError] = useState<Record<string, string | null>>(
    {},
  );

  const load = useCallback(async () => {
    setState('loading');
    try {
      const data = await suggestClients({ threshold });
      setResponse(data);
      // Pre-seed selection: include accounts with score >= soft cutoff.
      const nextSelected: Record<string, Record<string, boolean>> = {};
      data.groups.forEach((group) => {
        const perGroup: Record<string, boolean> = {};
        group.accounts.forEach((account) => {
          const key = `${account.platform}:${account.external_id}`;
          perGroup[key] = account.score >= SOFT_CONFIDENCE_CUTOFF;
        });
        nextSelected[group.group_id] = perGroup;
      });
      setSelectedAccounts(nextSelected);
      setState('ready');
    } catch (err) {
      setState('error');
      setError(err instanceof Error ? err.message : 'Unable to load suggestions.');
    }
  }, [threshold]);

  useEffect(() => {
    void load();
  }, [load]);

  const toggleAccount = useCallback(
    (groupId: string, accountKey: string) => {
      setSelectedAccounts((prev) => {
        const group = prev[groupId] ?? {};
        return {
          ...prev,
          [groupId]: { ...group, [accountKey]: !group[accountKey] },
        };
      });
    },
    [],
  );

  const handleApply = useCallback(
    async (group: SuggestedGroup) => {
      const groupId = group.group_id;
      const selection = selectedAccounts[groupId] ?? {};
      const accounts: AttachRequest[] = group.accounts
        .filter((account) => selection[`${account.platform}:${account.external_id}`])
        .map((account) => ({
          platform: account.platform,
          external_id: account.external_id,
          display_name: account.display_name || undefined,
        }));

      if (accounts.length === 0) {
        setApplyError((prev) => ({
          ...prev,
          [groupId]: 'Pick at least one account to attach.',
        }));
        return;
      }

      setApplying((prev) => ({ ...prev, [groupId]: true }));
      setApplyError((prev) => ({ ...prev, [groupId]: null }));
      try {
        const result = await applySuggestion({
          client_id: group.existing_client_id ?? undefined,
          create_name:
            group.existing_client_id ? undefined : (overrideName[groupId] || group.proposed_name),
          accounts,
        });
        navigate(`/clients/${result.client_id}`);
      } catch (err) {
        setApplyError((prev) => ({
          ...prev,
          [groupId]: err instanceof Error ? err.message : 'Unable to apply suggestion.',
        }));
      } finally {
        setApplying((prev) => ({ ...prev, [groupId]: false }));
      }
    },
    [navigate, overrideName, selectedAccounts],
  );

  const sortedGroups = useMemo<SuggestedGroup[]>(() => {
    if (!response?.groups) return [];
    // Existing-client matches first, then by descending avg confidence.
    return [...response.groups].sort((a, b) => {
      if (a.existing_client_id && !b.existing_client_id) return -1;
      if (!a.existing_client_id && b.existing_client_id) return 1;
      const avg = (g: SuggestedGroup) =>
        g.accounts.length === 0
          ? 0
          : g.accounts.reduce((acc, x) => acc + x.score, 0) / g.accounts.length;
      return avg(b) - avg(a);
    });
  }, [response]);

  if (state === 'loading') {
    return (
      <section className="phase2-page">
        <header className="phase2-page__header">
          <div>
            <p className="dashboardEyebrow">
              <Link to="/clients" className="phase2-link">
                ← Clients
              </Link>
            </p>
            <h1 className="dashboardHeading">Suggested client groups</h1>
          </div>
        </header>
        <SkeletonLoader variant="card" />
      </section>
    );
  }

  if (state === 'error') {
    return (
      <DashboardState
        variant="error"
        layout="page"
        title="Suggestions unavailable"
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
          <h1 className="dashboardHeading">Suggested client groups</h1>
          <p className="phase2-page__subhead">
            Name-matched candidates from your connected Meta ad accounts,
            Google Ads customers, and Meta pages. Apply a group to create (or
            extend) a Client with one click.
          </p>
        </div>
        <div className="phase2-row-actions">
          <label className="phase2-filter">
            <span>Threshold</span>
            <input
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={threshold}
              onChange={(event) => {
                const parsed = Number.parseFloat(event.target.value);
                if (Number.isFinite(parsed)) setThreshold(parsed);
              }}
            />
          </label>
          <button type="button" className="button secondary" onClick={() => void load()}>
            Refresh
          </button>
        </div>
      </header>

      {sortedGroups.length === 0 ? (
        <DashboardState
          variant="empty"
          layout="panel"
          title="Nothing to suggest"
          message="Every connected account is already attached to a Client, or no pairs cleared the similarity threshold. Lower the threshold or attach accounts manually."
        />
      ) : (
        <ul className="phase2-suggest-list" aria-label="Suggested groups">
          {sortedGroups.map((group) => {
            const selection = selectedAccounts[group.group_id] ?? {};
            const chosenCount = Object.values(selection).filter(Boolean).length;
            const isApplying = applying[group.group_id] === true;
            const errText = applyError[group.group_id] ?? null;
            const nameOverride = overrideName[group.group_id];
            return (
              <li
                key={group.group_id}
                className="phase2-card"
                aria-label={`Suggested group ${group.proposed_name}`}
              >
                <div className="phase2-card__header">
                  <h2>
                    {group.existing_client_id ? (
                      <>
                        Extend{' '}
                        <Link
                          to={`/clients/${group.existing_client_id}`}
                          className="phase2-link"
                        >
                          {group.existing_client_name ?? group.proposed_name}
                        </Link>
                      </>
                    ) : (
                      <>New client “{group.proposed_name}”</>
                    )}
                  </h2>
                  <span className="phase2-badge phase2-badge--muted">
                    {group.accounts.length} account
                    {group.accounts.length === 1 ? '' : 's'}
                  </span>
                </div>
                <div className="phase2-card__body">
                  {!group.existing_client_id && canApply ? (
                    <label className="phase2-filter">
                      <span>Override client name (optional)</span>
                      <input
                        type="text"
                        placeholder={group.proposed_name}
                        value={nameOverride ?? ''}
                        onChange={(event) =>
                          setOverrideName((prev) => ({
                            ...prev,
                            [group.group_id]: event.target.value,
                          }))
                        }
                        disabled={isApplying}
                      />
                    </label>
                  ) : null}
                  <table className="phase2-table" aria-label="Suggested accounts">
                    <thead>
                      <tr>
                        {canApply ? <th scope="col" aria-label="Include" /> : null}
                        <th scope="col">Platform</th>
                        <th scope="col">External ID</th>
                        <th scope="col">Display</th>
                        <th scope="col">Score</th>
                      </tr>
                    </thead>
                    <tbody>
                      {group.accounts.map((account) => {
                        const key = `${account.platform}:${account.external_id}`;
                        return (
                          <tr key={key}>
                            {canApply ? (
                              <td>
                                <input
                                  type="checkbox"
                                  checked={!!selection[key]}
                                  onChange={() => toggleAccount(group.group_id, key)}
                                  disabled={isApplying}
                                  aria-label={`Include ${account.display_name}`}
                                />
                              </td>
                            ) : null}
                            <td>
                              <span className="phase2-badge">
                                {platformLabel(account.platform)}
                              </span>
                            </td>
                            <td>
                              <code>{account.external_id}</code>
                            </td>
                            <td>{account.display_name || '—'}</td>
                            <td>{(account.score * 100).toFixed(0)}%</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                {canApply ? (
                  <div className="phase2-card__footer phase2-row">
                    <button
                      type="button"
                      className="button primary"
                      onClick={() => void handleApply(group)}
                      disabled={isApplying || chosenCount === 0}
                    >
                      {isApplying
                        ? 'Applying…'
                        : group.existing_client_id
                          ? `Attach ${chosenCount} to existing`
                          : `Create & attach ${chosenCount}`}
                    </button>
                    {errText ? (
                      <p className="phase2-card__error" role="alert">
                        {errText}
                      </p>
                    ) : null}
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}

      <p className="phase2-footnote">
        Similarity threshold: {(response?.threshold ?? threshold).toFixed(2)}.
        Suggestions are generated from platform account names — review before
        applying. Scores below {Math.round(SOFT_CONFIDENCE_CUTOFF * 100)}% are
        unchecked by default.
      </p>
    </section>
  );
};

export default ClientSuggestPage;
