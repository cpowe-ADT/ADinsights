import '../styles/skeleton.css';

type SkeletonVariant = 'card' | 'table' | 'text' | 'stat';

interface SkeletonLoaderProps {
  variant: SkeletonVariant;
  count?: number;
}

function CardSkeleton() {
  return <div className="skeleton skeleton--card" aria-hidden="true" />;
}

function TableSkeleton() {
  return (
    <div aria-hidden="true">
      {Array.from({ length: 5 }, (_, i) => (
        <div key={i} className="skeleton skeleton--table-row" />
      ))}
    </div>
  );
}

function TextSkeleton() {
  return (
    <div aria-hidden="true">
      {Array.from({ length: 3 }, (_, i) => (
        <div key={i} className="skeleton skeleton--text-line" />
      ))}
    </div>
  );
}

function StatSkeleton() {
  return (
    <div className="skeleton--stat" aria-hidden="true">
      <div className="skeleton skeleton--stat-box" />
      <div className="skeleton skeleton--stat-text" />
    </div>
  );
}

const variantMap: Record<SkeletonVariant, () => JSX.Element> = {
  card: CardSkeleton,
  table: TableSkeleton,
  text: TextSkeleton,
  stat: StatSkeleton,
};

export default function SkeletonLoader({ variant, count = 1 }: SkeletonLoaderProps) {
  const VariantComponent = variantMap[variant];

  return (
    <div className="skeleton-loader" role="status" aria-label="Loading">
      {Array.from({ length: count }, (_, i) => (
        <VariantComponent key={i} />
      ))}
    </div>
  );
}
