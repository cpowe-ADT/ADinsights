import type { CSSProperties, HTMLAttributes, ReactNode } from 'react';

interface ChartCardProps extends HTMLAttributes<HTMLElement> {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  footer?: ReactNode;
  minHeight?: number;
  children: ReactNode;
}

const ChartCard = ({
  title,
  description,
  actions,
  footer,
  minHeight = 280,
  children,
  className,
  style,
  ...sectionProps
}: ChartCardProps) => {
  const mergedClassName = ['panel', 'chart-card', className].filter(Boolean).join(' ');
  const mergedStyle = {
    ...style,
    '--chart-card-min-height': `${minHeight}px`,
  } as CSSProperties;

  return (
    <section className={mergedClassName} style={mergedStyle} {...sectionProps}>
      <header className="chart-card__header">
        <div>
          <h2>{title}</h2>
          {description ? <p className="muted">{description}</p> : null}
        </div>
        {actions ? <div className="chart-card__actions">{actions}</div> : null}
      </header>
      <div className="chart-card__body">
        <div className="chart-card__canvas">{children}</div>
      </div>
      {footer ? <footer className="chart-card__footer">{footer}</footer> : null}
    </section>
  );
};

export default ChartCard;
