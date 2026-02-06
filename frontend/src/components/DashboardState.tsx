import type { ReactNode } from 'react';

import EmptyState from './EmptyState';
import ErrorState from './ErrorState';

type DashboardStateVariant = 'loading' | 'empty' | 'no-results' | 'error';
type DashboardStateLayout = 'panel' | 'page' | 'compact';

interface DashboardStateProps {
  variant: DashboardStateVariant;
  title?: string;
  message?: string;
  actionLabel?: string;
  onAction?: () => void;
  actionVariant?: 'primary' | 'secondary' | 'tertiary';
  icon?: ReactNode;
  layout?: DashboardStateLayout;
  className?: string;
}

const DefaultEmptyIcon = () => (
  <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="2.2">
    <rect x="8" y="12" width="32" height="24" rx="4" />
    <path d="M14 20h20M14 28h12" strokeLinecap="round" />
  </svg>
);

const NoResultsIcon = () => (
  <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="2.2">
    <circle cx="20" cy="20" r="8" />
    <path d="m28 28 8 8" strokeLinecap="round" />
    <path d="M12 20h16" strokeLinecap="round" />
  </svg>
);

const classNames = (...values: Array<string | undefined | null | false>) =>
  values.filter(Boolean).join(' ');

const DashboardState = ({
  variant,
  title,
  message,
  actionLabel,
  onAction,
  actionVariant,
  icon,
  layout = 'panel',
  className,
}: DashboardStateProps) => {
  const layoutClass = `dashboard-state--${layout}`;
  const stateClass = `dashboard-state--${variant}`;
  const wrapperClass = classNames('dashboard-state', layoutClass, stateClass, className);

  if (variant === 'loading') {
    return (
      <div className={wrapperClass} role="status" aria-live="polite" aria-busy="true">
        <div className="dashboard-state__spinner" aria-hidden="true" />
        <p className="dashboard-state__message">{message ?? 'Loading dashboard data...'}</p>
      </div>
    );
  }

  if (variant === 'error') {
    return (
      <div className={wrapperClass}>
        <ErrorState
          title={title ?? 'Unable to load data'}
          message={message ?? 'Please try again in a moment.'}
          retryLabel={actionLabel ?? 'Retry load'}
          onRetry={onAction}
        />
      </div>
    );
  }

  const resolvedTitle =
    title ?? (variant === 'no-results' ? 'No results found' : 'No data yet');
  const resolvedMessage =
    message ??
    (variant === 'no-results'
      ? 'Try adjusting filters to widen the view.'
      : 'Data will appear once your next sync finishes.');
  const resolvedIcon =
    icon ?? (variant === 'no-results' ? <NoResultsIcon /> : <DefaultEmptyIcon />);
  const resolvedActionLabel =
    actionLabel ?? (variant === 'no-results' ? 'Clear filters' : 'Refresh data');
  const resolvedActionVariant =
    actionVariant ?? (variant === 'no-results' ? 'tertiary' : 'secondary');

  return (
    <div className={wrapperClass}>
      <EmptyState
        icon={resolvedIcon}
        title={resolvedTitle}
        message={resolvedMessage}
        actionLabel={onAction ? resolvedActionLabel : undefined}
        onAction={onAction}
        actionVariant={resolvedActionVariant}
      />
    </div>
  );
};

export default DashboardState;
