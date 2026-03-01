import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import DashboardState from '../components/DashboardState';
import EmptyState from '../components/EmptyState';
import { useTheme } from '../components/ThemeProvider';
import { fetchRecentDashboards, type RecentDashboard } from '../lib/recentDashboards';
import styles from './Home.module.css';

const BANNER_STORAGE_KEY = 'adinsights.home.banner.dismissed';
const DEFAULT_ANNOUNCEMENT = {
  id: 'release-notes-2024-09',
  title: 'Release notes are live',
  message: 'Catch the latest map updates, onboarding tweaks, and dashboard refinements.',
  ctaLabel: 'View release notes',
};

type QuickAction = {
  id: string;
  label: string;
  description: string;
  icon: JSX.Element;
  action: () => void;
};

type LoadState = 'loading' | 'ready' | 'error';

type ResourceLink = {
  id: string;
  label: string;
  description: string;
  href: string;
};

const LayoutIcon = () => (
  <svg
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    aria-hidden="true"
  >
    <rect x="3.5" y="4" width="17" height="16" rx="3" />
    <path d="M11 4v16" />
    <path d="M3.5 11h17" />
  </svg>
);

const CampaignIcon = () => (
  <svg
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    aria-hidden="true"
  >
    <rect x="4" y="4" width="16" height="16" rx="3" />
    <path d="M8 16v-4" strokeLinecap="round" />
    <path d="M12 16v-7" strokeLinecap="round" />
    <path d="M16 16v-2" strokeLinecap="round" />
  </svg>
);

const MapIcon = () => (
  <svg
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    aria-hidden="true"
  >
    <path d="M4.5 6.5 9 4l6 2.5 4.5-1.5V17L15 19.5 9 17 4.5 18.5Z" strokeLinejoin="round" />
    <path d="M9 4v13" />
    <path d="M15 6.5v13" />
  </svg>
);

const SocialIcon = () => (
  <svg
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    aria-hidden="true"
  >
    <circle cx="7" cy="8" r="2.5" />
    <circle cx="17" cy="8" r="2.5" />
    <circle cx="12" cy="16" r="2.5" />
    <path d="M9.2 9.4 10.8 14.6" strokeLinecap="round" />
    <path d="M14.8 9.4 13.2 14.6" strokeLinecap="round" />
  </svg>
);

const ArrowIcon = () => (
  <svg
    width="18"
    height="18"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    aria-hidden="true"
  >
    <path d="m8 5 8 7-8 7" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const CloseIcon = () => (
  <svg
    width="14"
    height="14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    aria-hidden="true"
  >
    <path d="M7 7l10 10" strokeLinecap="round" />
    <path d="M17 7l-10 10" strokeLinecap="round" />
  </svg>
);

const DashboardPlaceholderIcon = () => (
  <svg
    width="48"
    height="48"
    viewBox="0 0 48 48"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.2"
    aria-hidden="true"
  >
    <rect x="8" y="12" width="32" height="24" rx="3.5" />
    <path d="M8 22h32" strokeLinecap="round" />
    <path d="M18 12v24" strokeLinecap="round" />
    <circle cx="14" cy="18" r="1.8" fill="currentColor" stroke="none" />
    <circle cx="26" cy="30" r="1.8" fill="currentColor" stroke="none" />
  </svg>
);

const isExternalLink = (href: string) => /^https?:\/\//.test(href);

const resolveBooleanFlag = (value: unknown, defaultValue: boolean): boolean => {
  if (typeof value !== 'string') {
    return defaultValue;
  }
  const normalized = value.trim().toLowerCase();
  if (['1', 'true', 'yes', 'y', 'on'].includes(normalized)) {
    return true;
  }
  if (['0', 'false', 'no', 'n', 'off'].includes(normalized)) {
    return false;
  }
  return defaultValue;
};

const buildAnnouncementConfig = (releaseNotesUrl: string) => {
  const env = import.meta.env;
  return {
    enabled: resolveBooleanFlag(env.VITE_HOME_ANNOUNCEMENT_ENABLED, true),
    id: env.VITE_HOME_ANNOUNCEMENT_ID?.trim() || DEFAULT_ANNOUNCEMENT.id,
    title: env.VITE_HOME_ANNOUNCEMENT_TITLE?.trim() || DEFAULT_ANNOUNCEMENT.title,
    message: env.VITE_HOME_ANNOUNCEMENT_MESSAGE?.trim() || DEFAULT_ANNOUNCEMENT.message,
    ctaLabel: env.VITE_HOME_ANNOUNCEMENT_CTA_LABEL?.trim() || DEFAULT_ANNOUNCEMENT.ctaLabel,
    href: env.VITE_HOME_ANNOUNCEMENT_HREF?.trim() || releaseNotesUrl,
  };
};

const Home = () => {
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const docsUrl =
    import.meta.env.VITE_DOCS_URL?.trim() ||
    'https://github.com/cpowe-ADT/ADinsights/blob/main/docs/ops/doc-index.md';
  const csvDocsUrl =
    import.meta.env.VITE_DOCS_CSV_URL?.trim() ||
    import.meta.env.VITE_CSV_GUIDE_URL?.trim() ||
    'https://github.com/cpowe-ADT/ADinsights/blob/main/docs/runbooks/csv-uploads.md';
  const releaseNotesUrl =
    import.meta.env.VITE_RELEASE_NOTES_URL?.trim() ||
    'https://github.com/cpowe-ADT/ADinsights/blob/main/docs/ops/agent-activity-log.md';

  const announcementConfig = useMemo(
    () => buildAnnouncementConfig(releaseNotesUrl),
    [releaseNotesUrl],
  );

  const [isBannerVisible, setIsBannerVisible] = useState(announcementConfig.enabled);
  const [recentDashboards, setRecentDashboards] = useState<RecentDashboard[]>([]);
  const [dashboardsState, setDashboardsState] = useState<LoadState>('loading');

  useEffect(() => {
    if (!announcementConfig.enabled) {
      setIsBannerVisible(false);
      return;
    }
    if (typeof window === 'undefined') {
      return;
    }
    try {
      const dismissedId = window.localStorage.getItem(BANNER_STORAGE_KEY);
      setIsBannerVisible(dismissedId !== announcementConfig.id);
    } catch {
      setIsBannerVisible(true);
    }
  }, [announcementConfig.enabled, announcementConfig.id]);

  const handleDismissBanner = useCallback(() => {
    setIsBannerVisible(false);
    if (typeof window === 'undefined') {
      return;
    }
    try {
      window.localStorage.setItem(BANNER_STORAGE_KEY, announcementConfig.id);
    } catch {
      // Ignore storage write errors.
    }
  }, [announcementConfig.id]);

  useEffect(() => {
    let isActive = true;
    setDashboardsState('loading');
    void fetchRecentDashboards(3)
      .then((data) => {
        if (!isActive) {
          return;
        }
        setRecentDashboards(data);
        setDashboardsState('ready');
      })
      .catch(() => {
        if (!isActive) {
          return;
        }
        setRecentDashboards([]);
        setDashboardsState('error');
      });
    return () => {
      isActive = false;
    };
  }, []);

  const handleCreateDashboard = useCallback(() => {
    navigate('/dashboards/create');
  }, [navigate]);

  const handleViewCampaigns = useCallback(() => {
    navigate('/dashboards/campaigns');
  }, [navigate]);

  const handleOpenMap = useCallback(() => {
    navigate('/dashboards/map');
  }, [navigate]);

  const handleConnectSocials = useCallback(() => {
    navigate('/dashboards/data-sources?sources=social');
  }, [navigate]);

  const handleInvite = useCallback(() => {
    if (typeof window !== 'undefined') {
      window.open(
        'mailto:?subject=Join%20ADInsights&body=Let%27s%20collaborate%20on%20performance%20dashboards',
        '_self',
      );
    }
  }, []);

  const handleOpenDashboard = useCallback(
    (href: string) => {
      navigate(href);
    },
    [navigate],
  );

  const quickActions: QuickAction[] = useMemo(
    () => [
      {
        id: 'create-dashboard',
        label: 'Create dashboard',
        description: 'Start a new view with curated KPIs.',
        icon: <LayoutIcon />,
        action: handleCreateDashboard,
      },
      {
        id: 'view-campaigns',
        label: 'View campaigns',
        description: 'Review cross-channel performance in one place.',
        icon: <CampaignIcon />,
        action: handleViewCampaigns,
      },
      {
        id: 'open-map',
        label: 'Open map',
        description: 'Explore geo insights with the parish heatmap.',
        icon: <MapIcon />,
        action: handleOpenMap,
      },
      {
        id: 'connect-socials',
        label: 'Connect socials',
        description: 'Connect Facebook/Instagram and monitor connection health.',
        icon: <SocialIcon />,
        action: handleConnectSocials,
      },
    ],
    [handleConnectSocials, handleCreateDashboard, handleViewCampaigns, handleOpenMap],
  );

  const resourceLinks: ResourceLink[] = useMemo(
    () => [
      {
        id: 'docs-index',
        label: 'Docs index',
        description: 'Runbooks, ownership, and architectural references.',
        href: docsUrl,
      },
      {
        id: 'csv-guide',
        label: 'CSV upload guide',
        description: 'Templates and column rules for offline data.',
        href: csvDocsUrl,
      },
      {
        id: 'release-notes',
        label: 'Release notes',
        description: 'Shipped updates and planned improvements.',
        href: releaseNotesUrl,
      },
    ],
    [docsUrl, csvDocsUrl, releaseNotesUrl],
  );

  const hasDashboards = dashboardsState === 'ready' && recentDashboards.length > 0;
  const showAnnouncement = announcementConfig.enabled && isBannerVisible;
  const dashboardsEmptyTitle =
    dashboardsState === 'error' ? 'Recent dashboards unavailable' : 'No dashboards yet';
  const dashboardsEmptyMessage =
    dashboardsState === 'error'
      ? 'We could not load recent dashboards. Create your first dashboard to get started.'
      : 'Create your first dashboard to monitor campaign momentum and geo insights.';

  return (
    <div className={styles.homePage}>
      <div className="container">
        <section className={styles.heroBar} aria-labelledby="home-hero-title">
          <div className={styles.heroIntro}>
            <span className={styles.logoMark} aria-hidden="true">
              AD
            </span>
            <div>
              <h1 id="home-hero-title" className={styles.heroTitle}>
                ADInsights Analytics
              </h1>
              <p className={styles.heroSubtitle}>Multi-channel performance at a glance</p>
            </div>
          </div>
          <div className={styles.heroActions}>
            <button type="button" className={styles.primaryAction} onClick={handleCreateDashboard}>
              Create dashboard
            </button>
            <button
              type="button"
              className={styles.themeAction}
              onClick={toggleTheme}
              aria-pressed={theme === 'dark'}
              aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            >
              <span className={styles.themeActionIcon} aria-hidden="true">
                {theme === 'dark' ? '🌞' : '🌙'}
              </span>
              <span>{theme === 'dark' ? 'Light' : 'Dark'} mode</span>
            </button>
            <button type="button" className={styles.secondaryAction} onClick={handleInvite}>
              Invite teammate
            </button>
          </div>
        </section>

        {showAnnouncement && (
          <section className={styles.announcementBanner} aria-labelledby="announcement-title">
            <div className={styles.announcementContent}>
              <p className={styles.announcementEyebrow}>Feature announcement</p>
              <h2 id="announcement-title" className={styles.announcementTitle}>
                {announcementConfig.title}
              </h2>
              <p className={styles.announcementMessage}>{announcementConfig.message}</p>
            </div>
            <div className={styles.announcementActions}>
              <a
                className={styles.announcementCta}
                href={announcementConfig.href}
                target={isExternalLink(announcementConfig.href) ? '_blank' : undefined}
                rel={isExternalLink(announcementConfig.href) ? 'noopener noreferrer' : undefined}
              >
                {announcementConfig.ctaLabel}
                <ArrowIcon />
              </a>
              <button
                type="button"
                className={styles.announcementDismiss}
                onClick={handleDismissBanner}
              >
                <CloseIcon />
                Dismiss
              </button>
            </div>
          </section>
        )}

        <div className={styles.mainColumns}>
          <div className={styles.mainColumn}>
            <section aria-labelledby="quick-actions-title">
              <div className={styles.sectionHeader}>
                <h2 id="quick-actions-title" className={styles.sectionTitle}>
                  Quick actions
                </h2>
                <p className={styles.sectionSubtitle}>Stay fast with the essentials</p>
              </div>
              <ul className={styles.quickActions} role="list">
                {quickActions.map((action) => (
                  <li key={action.id} className={styles.quickActionItem}>
                    <button
                      type="button"
                      className={styles.quickActionCard}
                      onClick={action.action}
                    >
                      <span className={styles.quickActionIcon}>{action.icon}</span>
                      <p className={styles.quickActionLabel}>{action.label}</p>
                      <p className={styles.quickActionDescription}>{action.description}</p>
                    </button>
                  </li>
                ))}
              </ul>
            </section>

            <section aria-labelledby="recent-dashboards-title">
              <div className={styles.sectionHeader}>
                <h2 id="recent-dashboards-title" className={styles.sectionTitle}>
                  Recent dashboards
                </h2>
                <p className={styles.sectionSubtitle}>Jump back into your latest workspaces</p>
              </div>
              {dashboardsState === 'loading' ? (
                <DashboardState
                  variant="loading"
                  layout="compact"
                  message="Loading recent dashboards..."
                  className={styles.dashboardState}
                />
              ) : hasDashboards ? (
                <ul className={styles.dashboardGrid} role="list">
                  {recentDashboards.map((dashboard) => (
                    <li key={dashboard.id} className={styles.dashboardItem}>
                      <button
                        type="button"
                        className={styles.dashboardCard}
                        onClick={() => handleOpenDashboard(dashboard.href)}
                      >
                        <h3 className={styles.dashboardName}>{dashboard.name}</h3>
                        <dl className={styles.dashboardDetails}>
                          <div className={styles.dashboardDetail}>
                            <dt>Owner</dt>
                            <dd>{dashboard.owner}</dd>
                          </div>
                          <div className={styles.dashboardDetail}>
                            <dt>Last viewed</dt>
                            <dd>{dashboard.lastViewedLabel}</dd>
                          </div>
                        </dl>
                        <span className={styles.dashboardCta}>
                          Open dashboard
                          <ArrowIcon />
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState
                  icon={<DashboardPlaceholderIcon />}
                  title={dashboardsEmptyTitle}
                  message={dashboardsEmptyMessage}
                  actionLabel="Create dashboard"
                  onAction={handleCreateDashboard}
                  className={styles.emptyState}
                />
              )}
            </section>
          </div>

          <aside className={styles.sidebar} aria-label="Docs and releases">
            <section className={styles.resourceCard} aria-labelledby="resource-links-title">
              <div className={styles.resourceHeader}>
                <h2 id="resource-links-title" className={styles.resourceTitle}>
                  Docs and releases
                </h2>
                <p className={styles.resourceSummary}>
                  Keep the team aligned with the latest runbooks and release highlights.
                </p>
              </div>
              <ul className={styles.resourceList} role="list">
                {resourceLinks.map((link) => {
                  const isExternal = isExternalLink(link.href);
                  return (
                    <li key={link.id} className={styles.resourceItem}>
                      <a
                        className={styles.resourceLink}
                        href={link.href}
                        target={isExternal ? '_blank' : undefined}
                        rel={isExternal ? 'noopener noreferrer' : undefined}
                      >
                        <span className={styles.resourceText}>
                          <span className={styles.resourceLabel}>{link.label}</span>
                          <span className={styles.resourceDescription}>{link.description}</span>
                        </span>
                        <ArrowIcon />
                      </a>
                    </li>
                  );
                })}
              </ul>
            </section>
          </aside>
        </div>
      </div>
    </div>
  );
};

export default Home;
