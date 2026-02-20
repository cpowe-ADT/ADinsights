import type { MetricAvailabilityEntry } from '../lib/metaPageInsights';

type MetricAvailabilityBadgeProps = {
  metric: string;
  availability?: MetricAvailabilityEntry;
};

const MetricAvailabilityBadge = ({ metric, availability }: MetricAvailabilityBadgeProps) => {
  if (!availability || availability.supported) {
    return null;
  }
  return (
    <span className="meta-availability-badge" role="status" aria-label={`${metric} unavailable`}>
      Not available for this Page
    </span>
  );
};

export default MetricAvailabilityBadge;
