import type { ReactNode } from "react";

interface ErrorStateProps {
  title?: string;
  message: string;
  retryLabel?: string;
  onRetry?: () => void;
  className?: string;
  icon?: ReactNode;
}

const DefaultErrorIcon = () => (
  <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="2.5">
    <circle cx="24" cy="24" r="20" strokeOpacity="0.8" />
    <path d="M24 14v12" strokeLinecap="round" />
    <circle cx="24" cy="32" r="1.8" fill="currentColor" stroke="none" />
  </svg>
);

const ErrorState = ({
  title = "Something went wrong",
  message,
  retryLabel = "Try again",
  onRetry,
  className,
  icon,
}: ErrorStateProps) => {
  const classes = ["error-state", className].filter(Boolean).join(" ");

  return (
    <div className={classes} role="alert" aria-live="assertive">
      <div className="error-state__icon" aria-hidden="true">
        {icon ?? <DefaultErrorIcon />}
      </div>
      <div className="error-state__content">
        <h3>{title}</h3>
        <p>{message}</p>
      </div>
      {onRetry ? (
        <button type="button" className="button secondary" onClick={onRetry}>
          {retryLabel}
        </button>
      ) : null}
    </div>
  );
};

export default ErrorState;
