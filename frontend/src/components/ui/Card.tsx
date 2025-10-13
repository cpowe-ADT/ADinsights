import { ReactNode, useId } from 'react';

interface CardProps {
  title: string;
  className?: string;
  titleId?: string;
  children?: ReactNode;
}

const joinClassNames = (...values: Array<string | undefined>) => values.filter(Boolean).join(' ');

const Card = ({ title, className, titleId, children }: CardProps) => {
  const generatedId = useId();
  const headingId = titleId ?? `${generatedId}-title`;

  return (
    <section
      role="region"
      aria-labelledby={headingId}
      className={joinClassNames('card', className)}
    >
      <header className="cardHeader">
        <h2 id={headingId} className="cardTitle">
          {title}
        </h2>
      </header>
      <div className="content">{children}</div>
    </section>
  );
};

export default Card;
