import { ReactNode } from 'react'

import styles from './StatusMessage.module.css'

type StatusVariant = 'default' | 'muted' | 'error' | 'success'

interface StatusMessageProps {
  children: ReactNode
  variant?: StatusVariant
  role?: 'status' | 'alert'
  className?: string
}

const mergeClasses = (...tokens: Array<string | false | null | undefined>) =>
  tokens.filter(Boolean).join(' ')

const variantClassMap: Record<Exclude<StatusVariant, 'default'>, string> = {
  muted: styles.muted,
  error: styles.error,
  success: styles.success,
}

const StatusMessage = ({
  children,
  variant = 'default',
  role = 'status',
  className,
}: StatusMessageProps) => {
  const classes = mergeClasses(
    styles.message,
    variant === 'default' ? undefined : variantClassMap[variant],
    className,
  )

  return (
    <p role={role} className={classes}>
      {children}
    </p>
  )
}

export default StatusMessage
