import { NavLink, Outlet } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';

const AppShell = () => {
  const { logout, tenantId, user } = useAuth();
  const accountLabel = (user as { email?: string } | undefined)?.email ?? 'Signed in';
  const year = new Date().getFullYear();

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <header className="app-header" role="banner">
        <div className="app-boundary app-header__inner">
          <div className="app-brand">
            <span className="app-logo" aria-hidden="true">
              AD
            </span>
            <div>
              <p className="app-name">ADinsights</p>
              <p className="app-tenant">
                Tenant <strong>{tenantId ?? 'unknown'}</strong>
              </p>
            </div>
          </div>
          <div className="app-header-actions">
            <span className="app-user" aria-live="polite">
              {accountLabel}
            </span>
            <button type="button" className="button tertiary" onClick={logout}>
              Log out
            </button>
          </div>
        </div>
      </header>
      <nav className="app-nav" aria-label="Primary">
        <div className="app-boundary app-nav__inner">
          <NavLink to="/" end className={({ isActive }) => (isActive ? 'active' : undefined)}>
            Home
          </NavLink>
          <NavLink
            to="/dashboards/campaigns"
            className={({ isActive }) => (isActive ? 'active' : undefined)}
          >
            Campaigns
          </NavLink>
          <NavLink
            to="/dashboards/creatives"
            className={({ isActive }) => (isActive ? 'active' : undefined)}
          >
            Creatives
          </NavLink>
          <NavLink
            to="/dashboards/budget"
            className={({ isActive }) => (isActive ? 'active' : undefined)}
          >
            Budget pacing
          </NavLink>
        </div>
      </nav>
      <main id="main-content" className="app-main" tabIndex={-1}>
        <Outlet />
      </main>
      <footer className="app-footer">
        <p>© {year} ADinsights. All rights reserved.</p>
      </footer>
    </div>
  );
};

export default AppShell;
