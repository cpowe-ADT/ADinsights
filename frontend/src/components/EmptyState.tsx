import type { ReactNode } from 'react';

interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  message: string;
  actionLabel: string;
  onAction: () => void;
  actionVariant?: 'primary' | 'secondary' | 'tertiary';
  className?: string;
}

const EmptyState = ({
  icon,
  title,
  message,
  actionLabel,
  onAction,
  actionVariant = 'primary',
  className,
}: EmptyStateProps) => {
  const classes = ['empty-state', className].filter(Boolean).join(' ');
  const buttonClass = ['button', actionVariant].filter(Boolean).join(' ');

  return (
    <div className={classes} role="status" aria-live="polite">
      <div className="empty-state__icon" aria-hidden="true">
        {icon}
      </div>
      <div className="empty-state__content">
        <h3>{title}</h3>
        <p>{message}</p>
      </div>
      <button type="button" className={buttonClass} onClick={onAction}>
        {actionLabel}
      </button>
    </div>
  );
};

export default EmptyState;
