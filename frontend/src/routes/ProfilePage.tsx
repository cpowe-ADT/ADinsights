import { useCallback, useEffect, useState } from 'react';

import { useAuth } from '../auth/AuthContext';
import DashboardState from '../components/DashboardState';
import SkeletonLoader from '../components/SkeletonLoader';
import { useTheme } from '../components/ThemeProvider';
import { fetchProfile, type UserProfile } from '../lib/phase2Api';
import '../styles/phase2.css';
import '../styles/dashboard.css';
import '../styles/skeleton.css';

const ProfilePage = () => {
  const { logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [error, setError] = useState('Unable to load profile.');

  const load = useCallback(async () => {
    setState('loading');
    try {
      const data = await fetchProfile();
      setProfile(data);
      setState('ready');
    } catch (err) {
      setState('error');
      setError(err instanceof Error ? err.message : 'Unable to load profile.');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (state === 'loading') {
    return (
      <section className="phase2-page">
        <header className="phase2-page__header">
          <div>
            <p className="dashboardEyebrow">Account</p>
            <h1 className="dashboardHeading">My Profile</h1>
          </div>
        </header>
        <SkeletonLoader variant="card" count={3} />
      </section>
    );
  }

  if (state === 'error' || !profile) {
    return (
      <DashboardState
        variant="error"
        layout="page"
        title="Profile unavailable"
        message={error}
        actionLabel="Retry"
        onAction={() => void load()}
      />
    );
  }

  const { user, tenant_id } = profile;
  const fullName = [user.first_name, user.last_name].filter(Boolean).join(' ') || 'Unnamed user';

  return (
    <section className="phase2-page">
      <header className="phase2-page__header">
        <div>
          <p className="dashboardEyebrow">Account</p>
          <h1 className="dashboardHeading">My Profile</h1>
        </div>
        <div className="phase2-row-actions">
          <button type="button" className="button secondary" onClick={() => void load()}>
            Refresh
          </button>
        </div>
      </header>

      <article className="phase2-card">
        <h3>User info</h3>
        <p>
          Name: <strong>{fullName}</strong>
        </p>
        <p>
          Email: <strong>{user.email}</strong>
        </p>
        <p>
          Timezone: <strong>{user.timezone}</strong>
        </p>
        <p>
          Roles:{' '}
          {user.roles.length > 0 ? (
            user.roles.map((role) => (
              <span key={role} className="phase2-pill">
                {role}
              </span>
            ))
          ) : (
            <span className="muted">No roles assigned</span>
          )}
        </p>
        <p>
          Tenant ID: <strong>{tenant_id}</strong>
        </p>
      </article>

      <article className="phase2-card">
        <h3>Theme</h3>
        <p>
          Current theme: <strong>{theme}</strong>
        </p>
        <button
          type="button"
          className="button secondary"
          onClick={toggleTheme}
        >
          Switch to {theme === 'dark' ? 'light' : 'dark'} mode
        </button>
      </article>

      <article className="phase2-card">
        <h3>Session</h3>
        <button type="button" className="button secondary" onClick={logout}>
          Sign out
        </button>
      </article>
    </section>
  );
};

export default ProfilePage;
