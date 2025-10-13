import styles from './FullPageLoader.module.css'

interface FullPageLoaderProps {
  message?: string
}

const FullPageLoader = ({ message = 'Loading…' }: FullPageLoaderProps) => {
  return (
    <div className={styles.loader} role="status" aria-live="polite">
      <div className={styles.spinner} aria-hidden="true" />
      <p>{message}</p>
    </div>
  )
}

export default FullPageLoader
