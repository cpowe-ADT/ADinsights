import { useRouteError, isRouteErrorResponse } from 'react-router-dom';
import ErrorState from '../components/ErrorState';

export default function ErrorPage() {
  const error = useRouteError();
  console.error(error);

  let title = 'Unexpected Error';
  let message = 'An unexpected error has occurred.';

  if (isRouteErrorResponse(error)) {
    title = `${error.status} ${error.statusText}`;
    message = error.data?.message || 'Page not found or access denied.';
  } else if (error instanceof Error) {
    message = error.message;
  } else if (typeof error === 'string') {
    message = error;
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
        padding: '2rem',
        backgroundColor: 'var(--color-bg-subtle, #f9fafb)',
        color: 'var(--color-text, #111827)',
      }}
    >
      <div
        style={{
          maxWidth: '32rem',
          width: '100%',
          backgroundColor: 'var(--color-surface, #ffffff)',
          padding: '2rem',
          borderRadius: 'var(--radius-lg, 0.5rem)',
          boxShadow: 'var(--shadow-lg, 0 10px 15px -3px rgba(0, 0, 0, 0.1))',
        }}
      >
        <ErrorState
          title={title}
          message={message}
          onRetry={() => window.location.reload()}
          retryLabel="Reload Application"
        />
      </div>
    </div>
  );
}
