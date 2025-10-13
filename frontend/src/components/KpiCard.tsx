import Skeleton from "./Skeleton";

interface KpiCardProps {
  label: string;
  value: string;
  description?: string;
  isLoading?: boolean;
}

const KpiCard = ({ label, value, description, isLoading = false }: KpiCardProps) => {
  return (
    <div className="kpi-card" aria-busy={isLoading}>
      {isLoading ? (
        <div className="skeleton-stack">
          <Skeleton width="45%" height="0.75rem" />
          <Skeleton width="70%" height="1.9rem" />
          {description ? <Skeleton width="60%" height="0.85rem" /> : <Skeleton width="30%" height="0.65rem" />}
        </div>
      ) : (
        <>
          <p className="kpi-label">{label}</p>
          <p className="kpi-value">{value}</p>
          {description ? <p className="kpi-description">{description}</p> : null}
        </>
      )}
    </div>
  );
};

export default KpiCard;
