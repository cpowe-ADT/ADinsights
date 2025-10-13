import styles from './KpiCard.module.css'

interface KpiCardProps {
  label: string
  value: string
  description?: string
}

const KpiCard = ({ label, value, description }: KpiCardProps) => {
  return (
    <div className={styles.card}>
      <p className={styles.label}>{label}</p>
      <p className={styles.value}>{value}</p>
      {description ? <p className={styles.description}>{description}</p> : null}
    </div>
  )
}

export default KpiCard
