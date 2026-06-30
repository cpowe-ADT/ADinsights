import type { MetricAvailabilityEntry } from '../lib/metaPageInsights';

type MetricAvailabilityBadgeProps = {
  metric: string;
  availability?: MetricAvailabilityEntry;
};

const MetricAvailabilityBadge = ({ metric, availability }: MetricAvailabilityBadgeProps) => {
  if (!availability) {
    return null;
  }
  const state =
    availability.availability_state ?? (availability.supported ? 'available' : 'unsupported');
  if (state === 'available') {
    return null;
  }
  const label =
    state === 'callable_no_data'
      ? 'No stored data'
      : state === 'permission_gated'
        ? 'Permission gated'
        : 'Not available for this Page';
  const note = availability.availability_note || availability.reason || label;
  return (
    <span
      className="meta-availability-badge"
      role="status"
      aria-label={`${metric} ${label.toLowerCase()}`}
      title={note}
    >
      {label}
    </span>
  );
};

export default MetricAvailabilityBadge;
