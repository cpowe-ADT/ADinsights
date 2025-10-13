import { ReactNode } from 'react'

import styles from './DashboardShell.module.css'

const mergeClasses = (...tokens: Array<string | false | null | undefined>) =>
  tokens.filter(Boolean).join(' ')

type DashboardShellLayout = 'default' | 'single'

interface DashboardShellProps {
  children: ReactNode
  layout?: DashboardShellLayout
  className?: string
}

interface DashboardPanelProps {
  children: ReactNode
  fullWidth?: boolean
  className?: string
  as?: 'section' | 'div'
}

export const DashboardPanel = ({
  children,
  fullWidth,
  className,
  as: Element = 'section',
}: DashboardPanelProps) => {
  const classes = mergeClasses(styles.panel, fullWidth ? styles.fullWidth : undefined, className)
  return <Element className={classes}>{children}</Element>
}

const DashboardShell = ({ children, layout = 'default', className }: DashboardShellProps) => {
  const classes = mergeClasses(
    styles.shell,
    layout === 'single' ? styles.singleColumn : undefined,
    className,
  )
  return <div className={classes}>{children}</div>
}

export default DashboardShell
