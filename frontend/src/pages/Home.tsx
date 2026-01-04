import { useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';

import EmptyState from '../components/EmptyState';
import styles from './Home.module.css';

type QuickAction = {
  id: string;
  label: string;
  description: string;
  icon: JSX.Element;
  action: () => void;
};

type DashboardCard = {
  id: string;
  name: string;
  description: string;
  trend: number[];
  href: string;
};

const Sparkline = ({ points }: { points: number[] }) => {
  if (points.length === 0) {
    return null;
  }

  const max = Math.max(...points);
  const min = Math.min(...points);
  const range = max - min || 1;

  const coordinates = points.map((point, index) => {
    const x = points.length === 1 ? 50 : (index / (points.length - 1)) * 100;
    const y = 100 - ((point - min) / range) * 100;
    return `${index === 0 ? 'M' : 'L'}${x.toFixed(2)} ${y.toFixed(2)}`;
  });

  return (
    <div className={styles.sparkline} aria-hidden="true">
      <svg viewBox="0 0 100 100" role="presentation" focusable="false">
        <path d={coordinates.join(' ')} />
        {points.map((point, index) => {
          const x = points.length === 1 ? 50 : (index / (points.length - 1)) * 100;
          const y = 100 - ((point - min) / range) * 100;
          return <circle key={`dot-${index}`} cx={x} cy={y} r={1.8} />;
        })}
      </svg>
    </div>
  );
};

const ConnectIcon = () => (
  <svg
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
  >
    <path d="M6.5 12h11" strokeLinecap="round" />
    <path d="M8 15h8" strokeLinecap="round" />
    <path d="M8 9h8" strokeLinecap="round" />
    <rect x="3.5" y="4" width="17" height="16" rx="4" />
  </svg>
);

const LayoutIcon = () => (
  <svg
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
  >
    <rect x="3.5" y="4" width="17" height="16" rx="3" />
    <path d="M11 4v16" />
    <path d="M3.5 11h17" />
  </svg>
);

const UploadIcon = () => (
  <svg
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
  >
    <path d="M12 16V8" strokeLinecap="round" />
    <path d="M8.5 11.5 12 8l3.5 3.5" strokeLinecap="round" strokeLinejoin="round" />
    <rect x="4" y="4" width="16" height="16" rx="3.5" />
  </svg>
);

const BookIcon = () => (
  <svg
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
  >
    <path d="M5.5 4H18a1.5 1.5 0 0 1 1.5 1.5V20" strokeLinecap="round" />
    <path d="M5.5 4A1.5 1.5 0 0 0 4 5.5V20" strokeLinecap="round" />
    <path d="M9 8h6" strokeLinecap="round" />
    <path d="M9 12h6" strokeLinecap="round" />
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
  >
    <path d="m8 5 8 7-8 7" strokeLinecap="round" strokeLinejoin="round" />
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
  >
    <rect x="8" y="12" width="32" height="24" rx="3.5" />
    <path d="M8 22h32" strokeLinecap="round" />
    <path d="M18 12v24" strokeLinecap="round" />
    <circle cx="14" cy="18" r="1.8" fill="currentColor" stroke="none" />
    <circle cx="26" cy="30" r="1.8" fill="currentColor" stroke="none" />
  </svg>
);

const Home = () => {
  const navigate = useNavigate();
  const docsUrl =
    import.meta.env.VITE_DOCS_URL?.trim() ||
    'https://github.com/cpowe-ADT/ADinsights/blob/main/docs/ops/doc-index.md';
  const releaseNotesUrl =
    import.meta.env.VITE_RELEASE_NOTES_URL?.trim() ||
    'https://github.com/cpowe-ADT/ADinsights/blob/main/docs/ops/agent-activity-log.md';

  const handleCreateReport = useCallback(() => {
    navigate('/dashboards/campaigns');
  }, [navigate]);

  const handleInvite = useCallback(() => {
    if (typeof window !== 'undefined') {
      window.open(
        'mailto:?subject=Join%20ADInsights&body=Let%27s%20collaborate%20on%20performance%20dashboards',
        '_self',
      );
    }
  }, []);

  const handleViewDocs = useCallback(() => {
    if (typeof window !== 'undefined') {
      window.open(docsUrl, '_blank', 'noopener,noreferrer');
    }
  }, [docsUrl]);

  const quickActions: QuickAction[] = useMemo(
    () => [
      {
        id: 'connect',
        label: 'Connect data sources',
        description: 'Sync Meta, Google Ads, and offline conversions.',
        icon: <ConnectIcon />,
        action: () => navigate('/dashboards/campaigns'),
      },
      {
        id: 'dashboard',
        label: 'Create dashboard',
        description: 'Launch a tailored view in minutes.',
        icon: <LayoutIcon />,
        action: () => navigate('/dashboards/campaigns'),
      },
      {
        id: 'upload',
        label: 'Upload CSV',
        description: 'Augment insights with manual uploads.',
        icon: <UploadIcon />,
        action: () => navigate('/dashboards/campaigns'),
      },
      {
        id: 'docs',
        label: 'View docs',
        description: 'Explore best practices and release notes.',
        icon: <BookIcon />,
        action: handleViewDocs,
      },
    ],
    [handleViewDocs, navigate],
  );

  const recentDashboards: DashboardCard[] = useMemo(
    () => [
      {
        id: 'campaign-performance',
        name: 'Campaign performance',
        description: 'Cross-channel KPIs with spend, ROAS, and engagement.',
        trend: [32, 38, 35, 42, 47, 55],
        href: '/dashboards/campaigns',
      },
      {
        id: 'creative-performance',
        name: 'Creative insights',
        description: 'Identify winning creatives and audience resonance.',
        trend: [24, 22, 28, 31, 35, 37],
        href: '/dashboards/creatives',
      },
      {
        id: 'budget-pacing',
        name: 'Budget pacing',
        description: 'Forecast monthly pacing and guardrails by parish.',
        trend: [15, 18, 21, 20, 26, 29],
        href: '/dashboards/budget',
      },
    ],
    [],
  );

  const hasDashboards = recentDashboards.length > 0;

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
            <button type="button" className={styles.primaryAction} onClick={handleCreateReport}>
              Create report
            </button>
            <button type="button" className={styles.secondaryAction} onClick={handleInvite}>
              Invite teammate
            </button>
          </div>
        </section>

        <section aria-labelledby="quick-actions-title">
          <div className={styles.sectionHeader}>
            <h2 id="quick-actions-title" className={styles.sectionTitle}>
              Quick actions
            </h2>
            <p className={styles.sectionSubtitle}>Ship faster with curated shortcuts</p>
          </div>
          <ul className={styles.quickActions} role="list">
            {quickActions.map((action) => (
              <li key={action.id} className={styles.quickActionItem}>
                <button type="button" className={styles.quickActionCard} onClick={action.action}>
                  <span className={styles.quickActionIcon} aria-hidden="true">
                    {action.icon}
                  </span>
                  <p className={styles.quickActionLabel}>{action.label}</p>
                  <p className={styles.quickActionDescription}>{action.description}</p>
                </button>
              </li>
            ))}
          </ul>
        </section>

        <section className={styles.recentAndUpdates} aria-labelledby="recent-dashboards-title">
          <div>
            <div className={styles.sectionHeader}>
              <h2 id="recent-dashboards-title" className={styles.sectionTitle}>
                Recent dashboards
              </h2>
              <p className={styles.sectionSubtitle}>Jump back into your most-used workspaces</p>
            </div>
            {hasDashboards ? (
              <ul className={styles.dashboardGrid} role="list">
                {recentDashboards.map((dashboard) => (
                  <li key={dashboard.id} className={styles.dashboardItem}>
                    <article className={styles.dashboardCard}>
                      <Sparkline points={dashboard.trend} />
                      <div className={styles.dashboardMeta}>
                        <h3 className={styles.dashboardName}>{dashboard.name}</h3>
                        <p className={styles.dashboardDescription}>{dashboard.description}</p>
                      </div>
                      <button
                        type="button"
                        className={styles.openButton}
                        onClick={() => navigate(dashboard.href)}
                      >
                        Open
                      </button>
                    </article>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState
                icon={<DashboardPlaceholderIcon />}
                title="No dashboards yet"
                message="Create your first dashboard to unlock forecasting, pacing, and creative diagnostics in minutes."
                actionLabel="Build a dashboard"
                onAction={handleCreateReport}
              />
            )}
          </div>

          <aside className={styles.whatsNew} aria-labelledby="whats-new-title">
            <h2 id="whats-new-title" className={styles.whatsNewTitle}>
              What&apos;s new
            </h2>
            <p className={styles.whatsNewSummary}>
              Discover the latest releases and roadmap updates across the analytics suite.
            </p>
            <a
              className={styles.whatsNewLink}
              href={releaseNotesUrl}
              target="_blank"
              rel="noreferrer"
            >
              View release notes
              <ArrowIcon />
            </a>
          </aside>
        </section>
      </div>
    </div>
  );
};

export default Home;
