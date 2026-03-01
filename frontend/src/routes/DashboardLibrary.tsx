import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';

import EmptyState from '../components/EmptyState';
import ErrorState from '../components/ErrorState';
import FullPageLoader from '../components/FullPageLoader';
import { fetchDashboardLibrary, type DashboardLibraryItem } from '../lib/dashboardLibrary';

import '../styles/dashboard.css';

type LoadState = 'loading' | 'ready' | 'error';

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

const DashboardLibrary = () => {
  const navigate = useNavigate();
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

  const [items, setItems] = useState<DashboardLibraryItem[]>([]);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [ownerFilter, setOwnerFilter] = useState('all');

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
          setItems(data);
          setLoadState('ready');
        })
        .catch(() => {
          setLoadState('error');
        });
    }, 600);

    return () => window.clearTimeout(handle);
  }, [isForcedLoading, loadState]);

  const baseItems = useMemo(() => (isForcedEmpty ? [] : items), [isForcedEmpty, items]);

  const typeOptions = useMemo(() => {
    return Array.from(new Set(items.map((item) => item.type)));
  }, [items]);

  const ownerOptions = useMemo(() => {
    return Array.from(new Set(items.map((item) => item.owner)));
  }, [items]);

  const filteredItems = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();
    return baseItems.filter((item) => {
      const matchesSearch =
        normalizedSearch.length === 0 ||
        item.name.toLowerCase().includes(normalizedSearch) ||
        item.description.toLowerCase().includes(normalizedSearch) ||
        item.tags.some((tag) => tag.toLowerCase().includes(normalizedSearch)) ||
        item.owner.toLowerCase().includes(normalizedSearch);
      const matchesType = typeFilter === 'all' || item.type === typeFilter;
      const matchesOwner = ownerFilter === 'all' || item.owner === ownerFilter;
      return matchesSearch && matchesType && matchesOwner;
    });
  }, [baseItems, ownerFilter, search, typeFilter]);

  const hasFilters = search.trim().length > 0 || typeFilter !== 'all' || ownerFilter !== 'all';

  const handleClearFilters = () => {
    setSearch('');
    setTypeFilter('all');
    setOwnerFilter('all');
  };

  const handleRetry = () => {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete('state');
    setSearchParams(nextParams);
    setLoadState('loading');
  };

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

  const showLibraryEmpty = (isForcedEmpty || items.length === 0) && !hasFilters;

  if (showLibraryEmpty) {
    return (
      <EmptyState
        icon={<LibraryEmptyIcon />}
        title="No dashboards yet"
        message="Create your first dashboard to track performance and pacing."
        actionLabel="Create dashboard"
        onAction={() => navigate('/dashboards/create')}
      />
    );
  }

  return (
    <section className="dashboard-library">
      <header className="dashboard-library__header">
        <div>
          <p className="dashboardEyebrow">Dashboard library</p>
          <h1 className="dashboardHeading">Saved dashboards</h1>
          <p className="dashboard-library__subhead">
            Browse curated views, then jump straight into analysis.
          </p>
        </div>
        <Link className="button primary" to="/dashboards/create">
          Create dashboard
        </Link>
      </header>

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

      {filteredItems.length === 0 ? (
        <div className="dashboard-library__empty">
          <EmptyState
            icon={<LibraryEmptyIcon />}
            title="No dashboards match your filters"
            message="Try adjusting or clearing filters to find a saved dashboard."
            actionLabel="Clear filters"
            onAction={handleClearFilters}
            actionVariant="secondary"
          />
        </div>
      ) : (
        <div className="dashboard-library__grid">
          {filteredItems.map((item) => (
            <DashboardCard key={item.id} item={item} />
          ))}
        </div>
      )}
    </section>
  );
};

const DashboardCard = ({ item }: { item: DashboardLibraryItem }) => {
  const formattedDate = dateFormatter.format(new Date(item.updatedAt));

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
          Open dashboard
        </Link>
      </div>
    </article>
  );
};

export default DashboardLibrary;
