// @ts-nocheck

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import Breadcrumbs from '../components/Breadcrumbs';
import FilterBar, { FilterBarState } from '../components/FilterBar';
import { useTheme } from '../components/ThemeProvider';
import { useToast } from '../components/ToastProvider';
import { loadDashboardLayout, saveDashboardLayout } from '../lib/layoutPreferences';
import DatasetToggle from '../components/DatasetToggle';
import useDashboardStore from '../state/useDashboardStore';
import { useDatasetStore } from '../state/useDatasetStore';

const metricOptions = [
  { value: 'spend', label: 'Spend' },
  { value: 'impressions', label: 'Impressions' },
  { value: 'clicks', label: 'Clicks' },
  { value: 'conversions', label: 'Conversions' },
  { value: 'roas', label: 'ROAS' },
];

const segmentLabels: Record<string, string> = {
  dashboards: 'Dashboards',
  campaigns: 'Campaigns',
  creatives: 'Creatives',
  budget: 'Budget pacing',
};

const DashboardLayout = () => {
  const { tenantId, logout, user } = useAuth();
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();
  const { pushToast } = useToast();
  const [isScrolled, setIsScrolled] = useState(false);
  const datasetMode = useDatasetStore((state) => state.mode);
  const availableAdapters = useDatasetStore((state) => state.adapters);
  const hasDemoData = availableAdapters.includes('fake');
  const hasLiveData = availableAdapters.includes('warehouse');

  const handleFilterChange = useCallback((_: FilterBarState) => {
    // TODO: Connect filters to dashboard data fetching once APIs support it.
  }, []);

  const {
    loadAll,
    selectedMetric,
    setSelectedMetric,
    selectedParish,
    setSelectedParish,
    campaign,
    creative,
    budget,
    parish,
  } = useDashboardStore((state) => ({
    loadAll: state.loadAll,
    selectedMetric: state.selectedMetric,
    setSelectedMetric: state.setSelectedMetric,
    selectedParish: state.selectedParish,
    setSelectedParish: state.setSelectedParish,
    campaign: state.campaign,
    creative: state.creative,
    budget: state.budget,
    parish: state.parish,
  }));

  const layoutHydratedRef = useRef(false);

  useEffect(() => {
    void loadAll(tenantId);
  }, [loadAll, tenantId]);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 4);
    };

    handleScroll();
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  useEffect(() => {
    if (layoutHydratedRef.current) {
      return;
    }

    layoutHydratedRef.current = true;
    const storedLayout = loadDashboardLayout();
    if (!storedLayout) {
      return;
    }

    if (storedLayout.metric && storedLayout.metric !== selectedMetric) {
      setSelectedMetric(storedLayout.metric);
    }

    if (storedLayout.parish) {
      setSelectedParish(storedLayout.parish);
    }
  }, [selectedMetric, setSelectedMetric, setSelectedParish]);

  const errors = useMemo(() => {
    return [campaign, creative, budget, parish]
      .filter((slice) => slice.status === 'error' && slice.error)
      .map((slice) => slice.error as string);
  }, [budget, campaign, creative, parish]);

  const navLinks = useMemo(
    () => [
      { label: 'Campaigns', to: '/dashboards/campaigns', end: true },
      { label: 'Creatives', to: '/dashboards/creatives', end: true },
      { label: 'Budget pacing', to: '/dashboards/budget', end: true },
    ],
    [],
  );

  const breadcrumbs = useMemo(() => {
    const items: { label: string; to?: string }[] = [{ label: 'Home', to: '/' }];
    const segments = location.pathname.split('/').filter(Boolean);
    let pathAccumulator = '';

    segments.forEach((segment, index) => {
      pathAccumulator += `/${segment}`;
      const label = segmentLabels[segment] ?? segment.replace(/-/g, ' ');
      items.push({
        label: label.charAt(0).toUpperCase() + label.slice(1),
        to: index === segments.length - 1 ? undefined : pathAccumulator,
      });
    });

    return items;
  }, [location.pathname]);

  const handleSaveLayout = useCallback(() => {
    try {
      saveDashboardLayout({ metric: selectedMetric, parish: selectedParish });
      pushToast('Saved layout', { tone: 'success' });
    } catch (error) {
      pushToast('Unable to save layout', { tone: 'error' });
    }
  }, [pushToast, selectedMetric, selectedParish]);

  const handleCopyLink = useCallback(async () => {
    if (typeof window === 'undefined') {
      pushToast('Unable to copy link', { tone: 'error' });
      return;
    }

    const currentUrl = window.location.href;

    try {
      if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
        await navigator.clipboard.writeText(currentUrl);
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = currentUrl;
        textarea.setAttribute('aria-hidden', 'true');
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        textarea.style.pointerEvents = 'none';
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();
        const copied = document.execCommand('copy');
        document.body.removeChild(textarea);
        if (!copied) {
          throw new Error('Copy command failed');
        }
      }

      pushToast('Copied link', { tone: 'success' });
    } catch (error) {
      pushToast('Unable to copy link', { tone: 'error' });
    }
  }, [pushToast]);

  const SaveIcon = (
    <svg
      className="button-icon"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      aria-hidden="true"
    >
      <path d="M5 4h11l3 3v13H5z" />
      <path d="M9 4v5h6V4" />
      <path d="M9 13h6" strokeLinecap="round" />
    </svg>
  );

  const LinkIcon = (
    <svg
      className="button-icon"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      aria-hidden="true"
    >
      <path d="M10.5 7.5 9 6a4 4 0 0 0-5.66 5.66l2 2a4 4 0 0 0 5.66 0" />
      <path d="M13.5 16.5 15 18a4 4 0 0 0 5.66-5.66l-2-2a4 4 0 0 0-5.66 0" />
      <path d="m8 12 8 0" strokeLinecap="round" />
    </svg>
  );

  const accountLabel = (user as { email?: string } | undefined)?.email ?? 'Account';

  return (
    <div className="dashboard-shell">
      <div className={`dashboard-top${isScrolled ? ' shadow' : ''}`}>
        <header className="dashboard-header">
          <div className="container dashboard-header__inner">
            <div>
              <h1>ADinsights</h1>
              <p className="muted">
                Tenant <strong>{tenantId ?? 'unknown'}</strong>
                {selectedParish ? (
                  <span>
                    {' • '}Filtering to <strong>{selectedParish}</strong>
                  </span>
                ) : null}
              </p>
            </div>
            <div className="header-actions">
              <DatasetToggle />
              <label htmlFor="metric-select" className="muted">
                Map metric
              </label>
              <select
                id="metric-select"
                value={selectedMetric}
                onChange={(event) => setSelectedMetric(event.target.value as typeof selectedMetric)}
              >
                {metricOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="button tertiary theme-toggle"
                onClick={toggleTheme}
                aria-pressed={theme === 'dark'}
              >
                <span className="theme-toggle__icon" aria-hidden="true">
                  {theme === 'dark' ? '🌞' : '🌙'}
                </span>
                <span>{theme === 'dark' ? 'Light' : 'Dark'} mode</span>
              </button>
              <button type="button" className="button secondary" onClick={handleSaveLayout}>
                {SaveIcon}
                Save layout
              </button>
              <button
                type="button"
                className="button secondary"
                onClick={() => void handleCopyLink()}
              >
                {LinkIcon}
                Copy link
              </button>
              <span className="muted user-pill">{accountLabel}</span>
              <button type="button" className="button tertiary" onClick={logout}>
                Log out
              </button>
            </div>
          </div>
        </header>
        <nav className="dashboard-nav" aria-label="Dashboard sections">
          <div className="container dashboard-nav__inner">
            {navLinks.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.end}
                className={({ isActive }) => (isActive ? 'active' : undefined)}
              >
                {link.label}
              </NavLink>
            ))}
          </div>
        </nav>
        <Breadcrumbs items={breadcrumbs} />
      </div>
      <FilterBar onChange={handleFilterChange} />
      {datasetMode === 'dummy' ? (
        <div className="dashboard-status">
          <div className="container">
            <div className="status-message" role="status">
              Demo dataset is active. Toggle to view live warehouse metrics.
            </div>
          </div>
        </div>
      ) : null}
      {datasetMode === 'live' && !hasLiveData ? (
        <div className="dashboard-status">
          <div className="container">
            <div className="status-message" role="alert">
              Live warehouse metrics are unavailable. Switch to demo data to explore the
              interface.
            </div>
          </div>
        </div>
      ) : null}
      {errors.length > 0 ? (
        <div className="dashboard-status">
          <div className="container">
            <div className="status-message error" role="alert">
              {errors.map((message, index) => (
                <span key={`${message}-${index}`}>{message}</span>
              ))}
            </div>
          </div>
        </div>
      ) : null}
      <main className="dashboard-content">
        <div className="container">
          <Outlet />
        </div>
      </main>
    </div>
  );
};

export default DashboardLayout;
