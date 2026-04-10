import { Link } from 'react-router-dom';

export default function NotFoundPage() {
  return (
    <section
      className="phase2-page"
      style={{
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
        padding: '2rem',
        backgroundColor: 'var(--color-bg-subtle, #f9fafb)',
      }}
    >
      <div
        className="phase2-card"
        style={{ maxWidth: '32rem', width: '100%', textAlign: 'center' }}
      >
        <h1 style={{ margin: 0 }}>Page not found</h1>
        <p className="phase2-note">
          The page you're looking for doesn't exist or has been moved.
        </p>
        <div>
          <Link to="/dashboards" className="button primary">
            Go to dashboard
          </Link>
        </div>
      </div>
    </section>
  );
}
