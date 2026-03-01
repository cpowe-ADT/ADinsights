import type { ReactNode } from 'react';

type StatusBannerTone = 'info' | 'warning' | 'error';

interface StatusBannerProps {
  message: ReactNode;
  tone?: StatusBannerTone;
  className?: string;
  ariaLabel?: string;
  title?: string;
  icon?: ReactNode;
}

const classNames = (...values: Array<string | undefined | null | false>) =>
  values.filter(Boolean).join(' ');

const StatusBanner = ({
  message,
  tone = 'info',
  className,
  ariaLabel,
  title,
  icon,
}: StatusBannerProps) => {
  const role = tone === 'error' ? 'alert' : 'status';
  const ariaLive = tone === 'error' ? 'assertive' : 'polite';
  const classes = classNames('status-banner', `status-banner--${tone}`, className);

  return (
    <div className={classes} role={role} aria-live={ariaLive} aria-label={ariaLabel} title={title}>
      {icon ? (
        <span className="status-banner__icon" aria-hidden="true">
          {icon}
        </span>
      ) : null}
      <span className="status-banner__text">{message}</span>
    </div>
  );
};

export default StatusBanner;
