interface SnapshotIndicatorProps {
  label: string;
  tone?: 'fresh' | 'stale' | 'pending' | 'demo';
  timestamp?: string | null;
}

const SnapshotIndicator = ({ label, tone = 'fresh', timestamp }: SnapshotIndicatorProps) => {
  return (
    <div
      className={`snapshot-indicator snapshot-indicator--${tone}`}
      title={timestamp ?? undefined}
      role="status"
      aria-live="polite"
    >
      <span className="snapshot-indicator__dot" aria-hidden="true" />
      <span className="snapshot-indicator__text">{label}</span>
    </div>
  );
};

export default SnapshotIndicator;
