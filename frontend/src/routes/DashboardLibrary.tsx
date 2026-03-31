import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import EmptyState from '../components/EmptyState';
import ErrorState from '../components/ErrorState';
import FullPageLoader from '../components/FullPageLoader';
import {
  fetchDashboardLibrary,
  type DashboardLibraryItem,
  type DashboardLibraryResponse,
} from '../lib/dashboardLibrary';
import { canAccessCreatorUi } from '../lib/rbac';
import {
  deleteDashboardDefinition,
  duplicateDashboardDefinition,
  updateDashboardDefinition,
  type DashboardDefinition,
} from '../lib/phase2Api';
import { getDashboardTemplate } from '../lib/dashboardTemplates';

import '../styles/dashboard.css';

type LoadState = 'loading' | 'ready' | 'error';
type DashboardAction = 'rename' | 'duplicate' | 'archive' | 'delete';

const EMPTY_LIBRARY: DashboardLibraryResponse = {
  generatedAt: '',
  systemTemplates: [],
  savedDashboards: [],
};

const LibraryEmptyIcon = () => (
  <svg
    width="48"
    height="48"
    viewBox="0 0 48 48"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.2"
  >
    <rect x="10" y="12" width="28" height="24" rx="4" />
    <path d="M16 20h16" strokeLinecap="round" />
    <path d="M16 26h10" strokeLinecap="round" />
    <circle cx="34" cy="30" r="3.5" />
  </svg>
);

const dateFormatter = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
});

function normalizeOwner(definition: DashboardDefinition): string {
  return definition.owner_email?.trim() || 'Team';
}

function toSavedDashboardItem(definition: DashboardDefinition): DashboardLibraryItem {
  return {
    id: definition.id,
    kind: 'saved_dashboard',
    templateKey: definition.template_key,
    name: definition.name,
    type: getDashboardTemplate(definition.template_key).label,
    owner: normalizeOwner(definition),
    updatedAt: definition.updated_at,
    tags: [definition.default_metric.toUpperCase(), 'Meta Ads'],
    description: definition.description || 'Saved dashboard configuration.',
    route: `/dashboards/saved/${definition.id}`,
    defaultMetric: definition.default_metric,
    isActive: definition.is_active,
  };
}

function matchesLibraryItem(
  item: DashboardLibraryItem,
  filters: {
    search: string;
    typeFilter: string;
    ownerFilter: string;
  },
): boolean {
  const { search, typeFilter, ownerFilter } = filters;
  const normalizedSearch = search.trim().toLowerCase();
  const matchesSearch =
    normalizedSearch.length === 0 ||
    item.name.toLowerCase().includes(normalizedSearch) ||
    item.description.toLowerCase().includes(normalizedSearch) ||
    item.tags.some((tag) => tag.toLowerCase().includes(normalizedSearch)) ||
    item.owner.toLowerCase().includes(normalizedSearch);
  const matchesType = typeFilter === 'all' || item.type === typeFilter;
  const matchesOwner = ownerFilter === 'all' || item.owner === ownerFilter;
  return matchesSearch && matchesType && matchesOwner;
}

const DashboardLibrary = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const canCreate = canAccessCreatorUi(user);
  const [searchParams, setSearchParams] = useSearchParams();
  const forcedState = searchParams.get('state')?.toLowerCase() ?? '';
  const isForcedLoading = forcedState === 'loading';
  const isForcedError = forcedState === 'error';
  const isForcedEmpty = forcedState === 'empty';

  const [loadState, setLoadState] = useState<LoadState>(() => {
    if (isForcedError) {
      return 'error';
    }
    return 'loading';
  });
  const [library, setLibrary] = useState<DashboardLibraryResponse>(EMPTY_LIBRARY);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [ownerFilter, setOwnerFilter] = useState('all');
  const [actionError, setActionError] = useState<string>();
  const [pendingActionKey, setPendingActionKey] = useState<string>();

  useEffect(() => {
    if (isForcedError) {
      setLoadState('error');
      return;
    }
    if (isForcedLoading) {
      setLoadState('loading');
      return;
    }
    if (loadState === 'error') {
      setLoadState('loading');
    }
  }, [isForcedError, isForcedLoading, loadState]);

  useEffect(() => {
    if (loadState !== 'loading' || isForcedLoading) {
      return;
    }

    const handle = window.setTimeout(() => {
      void fetchDashboardLibrary()
        .then((data) => {
          setLibrary(data);
          setLoadState('ready');
        })
        .catch(() => {
          setLoadState('error');
        });
    }, 600);

    return () => window.clearTimeout(handle);
  }, [isForcedLoading, loadState]);

  const baseSystemTemplates = useMemo(
    () => (isForcedEmpty ? [] : library.systemTemplates),
    [isForcedEmpty, library.systemTemplates],
  );
  const baseSavedDashboards = useMemo(
    () => (isForcedEmpty ? [] : library.savedDashboards),
    [isForcedEmpty, library.savedDashboards],
  );
  const allItems = useMemo(
    () => [...baseSystemTemplates, ...baseSavedDashboards],
    [baseSavedDashboards, baseSystemTemplates],
  );

  const typeOptions = useMemo(
    () => Array.from(new Set(allItems.map((item) => item.type))),
    [allItems],
  );
  const ownerOptions = useMemo(
    () => Array.from(new Set(allItems.map((item) => item.owner))),
    [allItems],
  );

  const filteredSystemTemplates = useMemo(
    () =>
      baseSystemTemplates.filter((item) =>
        matchesLibraryItem(item, { search, typeFilter, ownerFilter }),
      ),
    [baseSystemTemplates, ownerFilter, search, typeFilter],
  );
  const filteredSavedDashboards = useMemo(
    () =>
      baseSavedDashboards.filter((item) =>
        matchesLibraryItem(item, { search, typeFilter, ownerFilter }),
      ),
    [baseSavedDashboards, ownerFilter, search, typeFilter],
  );

  const hasFilters = search.trim().length > 0 || typeFilter !== 'all' || ownerFilter !== 'all';
  const hasAnyItems = allItems.length > 0;
  const hasMatches =
    filteredSystemTemplates.length > 0 || filteredSavedDashboards.length > 0;

  const handleClearFilters = useCallback(() => {
    setSearch('');
    setTypeFilter('all');
    setOwnerFilter('all');
  }, []);

  const handleRetry = useCallback(() => {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete('state');
    setSearchParams(nextParams);
    setLoadState('loading');
  }, [searchParams, setSearchParams]);

  const updateSavedDashboards = useCallback(
    (
      updater: (
        current: DashboardLibraryResponse['savedDashboards'],
      ) => DashboardLibraryResponse['savedDashboards'],
    ) => {
      setLibrary((current) => ({
        ...current,
        savedDashboards: updater(current.savedDashboards),
      }));
    },
    [],
  );

  const runSavedDashboardAction = useCallback(
    async (
      item: DashboardLibraryItem,
      action: DashboardAction,
      callback: () => Promise<void>,
    ) => {
      setActionError(undefined);
      setPendingActionKey(`${action}:${item.id}`);
      try {
        await callback();
      } catch (error) {
        setActionError(error instanceof Error ? error.message : 'Dashboard action failed.');
      } finally {
        setPendingActionKey(undefined);
      }
    },
    [],
  );

  const handleRename = useCallback(
    async (item: DashboardLibraryItem) => {
      const nextName = window.prompt('Rename dashboard', item.name);
      const trimmed = nextName?.trim();
      if (!trimmed || trimmed === item.name) {
        return;
      }
      await runSavedDashboardAction(item, 'rename', async () => {
        const updated = await updateDashboardDefinition(item.id, { name: trimmed });
        updateSavedDashboards((current) =>
          current.map((entry) =>
            entry.id === item.id ? toSavedDashboardItem(updated) : entry,
          ),
        );
      });
    },
    [runSavedDashboardAction, updateSavedDashboards],
  );

  const handleDuplicate = useCallback(
    async (item: DashboardLibraryItem) => {
      await runSavedDashboardAction(item, 'duplicate', async () => {
        const duplicated = await duplicateDashboardDefinition(item.id);
        updateSavedDashboards((current) => [toSavedDashboardItem(duplicated), ...current]);
      });
    },
    [runSavedDashboardAction, updateSavedDashboards],
  );

  const handleArchive = useCallback(
    async (item: DashboardLibraryItem) => {
      const confirmed = window.confirm(`Archive "${item.name}" from the dashboard library?`);
      if (!confirmed) {
        return;
      }
      await runSavedDashboardAction(item, 'archive', async () => {
        await updateDashboardDefinition(item.id, { is_active: false });
        updateSavedDashboards((current) => current.filter((entry) => entry.id !== item.id));
      });
    },
    [runSavedDashboardAction, updateSavedDashboards],
  );

  const handleDelete = useCallback(
    async (item: DashboardLibraryItem) => {
      const confirmed = window.confirm(`Delete "${item.name}" permanently?`);
      if (!confirmed) {
        return;
      }
      await runSavedDashboardAction(item, 'delete', async () => {
        await deleteDashboardDefinition(item.id);
        updateSavedDashboards((current) => current.filter((entry) => entry.id !== item.id));
      });
    },
    [runSavedDashboardAction, updateSavedDashboards],
  );

  if (loadState === 'loading') {
    return <FullPageLoader message="Loading dashboards..." />;
  }

  if (loadState === 'error') {
    return (
      <ErrorState
        title="Dashboard library unavailable"
        message="We could not load the dashboard list. Try again or check back soon."
        onRetry={handleRetry}
      />
    );
  }

  const showLibraryEmpty = (isForcedEmpty || !hasAnyItems) && !hasFilters;

  if (showLibraryEmpty) {
    return (
      <EmptyState
        icon={<LibraryEmptyIcon />}
        title="No dashboards yet"
        message="Create your first dashboard to track performance and pacing."
        actionLabel={canCreate ? 'Create dashboard' : undefined}
        onAction={canCreate ? () => navigate('/dashboards/create') : undefined}
      />
    );
  }

  return (
    <section className="dashboard-library">
      <header className="dashboard-library__header">
        <div>
          <p className="dashboardEyebrow">Dashboard library</p>
          <h1 className="dashboardHeading">Meta dashboards</h1>
          <p className="dashboard-library__subhead">
            Start from a system template or open a saved dashboard backed by live warehouse data.
          </p>
        </div>
        {canCreate ? (
          <Link className="button primary" to="/dashboards/create">
            Create dashboard
          </Link>
        ) : null}
      </header>

      {actionError ? (
        <div className="dashboard-library__banner" role="alert">
          {actionError}
        </div>
      ) : null}

      <div className="dashboard-library__filters">
        <label className="library-field" htmlFor="library-search">
          <span className="library-field__label">Search</span>
          <input
            id="library-search"
            type="search"
            placeholder="Search dashboards, tags, or owners"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <label className="library-field" htmlFor="library-type">
          <span className="library-field__label">Type</span>
          <select
            id="library-type"
            value={typeFilter}
            onChange={(event) => setTypeFilter(event.target.value)}
          >
            <option value="all">All types</option>
            {typeOptions.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </label>
        <label className="library-field" htmlFor="library-owner">
          <span className="library-field__label">Owner</span>
          <select
            id="library-owner"
            value={ownerFilter}
            onChange={(event) => setOwnerFilter(event.target.value)}
          >
            <option value="all">All owners</option>
            {ownerOptions.map((owner) => (
              <option key={owner} value={owner}>
                {owner}
              </option>
            ))}
          </select>
        </label>
        <div className="library-field library-field__actions">
          <button
            type="button"
            className="button tertiary"
            onClick={handleClearFilters}
            disabled={!hasFilters}
          >
            Clear filters
          </button>
        </div>
      </div>

      {!hasMatches ? (
        <div className="dashboard-library__empty">
          <EmptyState
            icon={<LibraryEmptyIcon />}
            title="No dashboards match your filters"
            message="Try adjusting or clearing filters to find a dashboard."
            actionLabel="Clear filters"
            onAction={handleClearFilters}
            actionVariant="secondary"
          />
        </div>
      ) : (
        <>
          <DashboardSection
            title="System templates"
            description="Opinionated starting points for Meta Ads reporting."
            emptyMessage="No templates match the current filters."
            items={filteredSystemTemplates}
          />
          <DashboardSection
            title="Saved dashboards"
            description="Tenant-scoped Meta dashboards saved from the builder."
            emptyMessage="No saved dashboards match the current filters."
            items={filteredSavedDashboards}
            canManage={canCreate}
            pendingActionKey={pendingActionKey}
            onRename={handleRename}
            onDuplicate={handleDuplicate}
            onArchive={handleArchive}
            onDelete={handleDelete}
          />
        </>
      )}
    </section>
  );
};

type DashboardSectionProps = {
  title: string;
  description: string;
  emptyMessage: string;
  items: DashboardLibraryItem[];
  canManage?: boolean;
  pendingActionKey?: string;
  onRename?: (item: DashboardLibraryItem) => void | Promise<void>;
  onDuplicate?: (item: DashboardLibraryItem) => void | Promise<void>;
  onArchive?: (item: DashboardLibraryItem) => void | Promise<void>;
  onDelete?: (item: DashboardLibraryItem) => void | Promise<void>;
};

const DashboardSection = ({
  title,
  description,
  emptyMessage,
  items,
  canManage = false,
  pendingActionKey,
  onRename,
  onDuplicate,
  onArchive,
  onDelete,
}: DashboardSectionProps) => {
  return (
    <section className="dashboard-library__section">
      <header className="dashboard-library__section-header">
        <div>
          <h2 className="dashboard-library__section-title">{title}</h2>
          <p className="dashboard-library__section-copy">{description}</p>
        </div>
      </header>

      {items.length === 0 ? (
        <div className="dashboard-library__section-empty">
          <p>{emptyMessage}</p>
        </div>
      ) : (
        <div className="dashboard-library__grid">
          {items.map((item) => (
            <DashboardCard
              key={item.id}
              item={item}
              canManage={canManage && item.kind === 'saved_dashboard'}
              pendingActionKey={pendingActionKey}
              onRename={onRename}
              onDuplicate={onDuplicate}
              onArchive={onArchive}
              onDelete={onDelete}
            />
          ))}
        </div>
      )}
    </section>
  );
};

type DashboardCardProps = {
  item: DashboardLibraryItem;
  canManage: boolean;
  pendingActionKey?: string;
  onRename?: (item: DashboardLibraryItem) => void | Promise<void>;
  onDuplicate?: (item: DashboardLibraryItem) => void | Promise<void>;
  onArchive?: (item: DashboardLibraryItem) => void | Promise<void>;
  onDelete?: (item: DashboardLibraryItem) => void | Promise<void>;
};

const DashboardCard = ({
  item,
  canManage,
  pendingActionKey,
  onRename,
  onDuplicate,
  onArchive,
  onDelete,
}: DashboardCardProps) => {
  const formattedDate = dateFormatter.format(new Date(item.updatedAt));
  const isPending = (action: DashboardAction) => pendingActionKey === `${action}:${item.id}`;

  return (
    <article className="library-card">
      <header className="library-card__header">
        <div>
          <p className="library-card__eyebrow">{item.type}</p>
          <h3 className="library-card__title">{item.name}</h3>
        </div>
        <span className="library-owner" title={`Owner: ${item.owner}`}>
          {item.owner}
        </span>
      </header>
      <p className="library-card__description">{item.description}</p>
      <div className="library-card__tags">
        {item.tags.map((tag) => (
          <span key={`${item.id}-${tag}`} className="library-tag">
            {tag}
          </span>
        ))}
      </div>
      <div className="library-card__meta">
        <span className="library-card__meta-label">Last updated</span>
        <span className="library-card__meta-value">{formattedDate}</span>
      </div>
      <div className="library-card__actions">
        <Link className="button secondary" to={item.route}>
          {item.kind === 'system_template' ? 'Use template' : 'Open'}
        </Link>
        {canManage ? (
          <>
            <button
              type="button"
              className="button tertiary"
              onClick={() => onRename?.(item)}
              disabled={Boolean(pendingActionKey)}
            >
              {isPending('rename') ? 'Renaming…' : 'Rename'}
            </button>
            <button
              type="button"
              className="button tertiary"
              onClick={() => onDuplicate?.(item)}
              disabled={Boolean(pendingActionKey)}
            >
              {isPending('duplicate') ? 'Duplicating…' : 'Duplicate'}
            </button>
            <button
              type="button"
              className="button tertiary"
              onClick={() => onArchive?.(item)}
              disabled={Boolean(pendingActionKey)}
            >
              {isPending('archive') ? 'Archiving…' : 'Archive'}
            </button>
            <button
              type="button"
              className="button tertiary"
              onClick={() => onDelete?.(item)}
              disabled={Boolean(pendingActionKey)}
            >
              {isPending('delete') ? 'Deleting…' : 'Delete'}
            </button>
          </>
        ) : null}
      </div>
    </article>
  );
};

export default DashboardLibrary;
