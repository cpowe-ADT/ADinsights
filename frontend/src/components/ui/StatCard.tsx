import Metric from '../Metric';

export interface StatCardProps {
  label: string;
  value: string | number;
  sparkline?: number[];
}

const StatCard = ({ label, value, sparkline }: StatCardProps) => (
  <Metric label={label} value={value} trend={sparkline} className="metric-card--compact" />
);

export default StatCard;
