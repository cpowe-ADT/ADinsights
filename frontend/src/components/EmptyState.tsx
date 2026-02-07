import type { ReactNode } from 'react';

interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
  actionVariant?: 'primary' | 'secondary' | 'tertiary';
  secondaryActionLabel?: string;
  onSecondaryAction?: () => void;
  secondaryActionVariant?: 'primary' | 'secondary' | 'tertiary';
  className?: string;
}

const EmptyState = ({
  icon,
  title,
  message,
  actionLabel,
  onAction,
  actionVariant = 'primary',
  secondaryActionLabel,
  onSecondaryAction,
  secondaryActionVariant = 'tertiary',
  className,
}: EmptyStateProps) => {
  const classes = ['empty-state', className].filter(Boolean).join(' ');
  const buttonClass = ['button', actionVariant].filter(Boolean).join(' ');
  const secondaryButtonClass = ['button', secondaryActionVariant].filter(Boolean).join(' ');
  const showPrimaryAction = Boolean(actionLabel && onAction);
  const showSecondaryAction = Boolean(secondaryActionLabel && onSecondaryAction);
  const showActions = showPrimaryAction || showSecondaryAction;

  return (
    <div className={classes} role="status" aria-live="polite">
      <div className="empty-state__icon" aria-hidden="true">
        {icon}
      </div>
      <div className="empty-state__content">
        <h3>{title}</h3>
        <p>{message}</p>
      </div>
      {showActions ? (
        <div className="empty-state__actions">
          {showPrimaryAction ? (
            <button type="button" className={buttonClass} onClick={onAction}>
              {actionLabel}
            </button>
          ) : null}
          {showSecondaryAction ? (
            <button type="button" className={secondaryButtonClass} onClick={onSecondaryAction}>
              {secondaryActionLabel}
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
};

export default EmptyState;
