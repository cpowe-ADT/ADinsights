interface KpiCardProps {
  label: string;
  value: string;
  description?: string;
}

const KpiCard = ({ label, value, description }: KpiCardProps) => {
  return (
    <div className="kpi-card">
      <p className="kpi-label">{label}</p>
      <p className="kpi-value">{value}</p>
      {description ? <p className="kpi-description">{description}</p> : null}
    </div>
  );
};

export default KpiCard;
