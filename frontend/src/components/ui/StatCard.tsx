import Metric from '../Metric';

export interface StatCardProps {
  label: string;
  value: string | number;
  sparkline?: number[];
  tooltip?: string;
}

const StatCard = ({ label, value, sparkline, tooltip }: StatCardProps) => (
  <Metric
    label={label}
    value={value}
    tooltip={tooltip}
    trend={sparkline}
    className="metric-card--compact"
  />
);

export default StatCard;
