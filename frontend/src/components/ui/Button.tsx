import { ButtonHTMLAttributes, ForwardedRef, forwardRef } from 'react'

import styles from './Button.module.css'

type ButtonVariant = 'primary' | 'secondary' | 'tertiary' | 'link'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
}

const mergeClasses = (...tokens: Array<string | false | null | undefined>) =>
  tokens.filter(Boolean).join(' ')

const Button = (
  { variant = 'primary', className, type = 'button', ...props }: ButtonProps,
  ref: ForwardedRef<HTMLButtonElement>,
) => {
  const classes = mergeClasses(styles.button, styles[variant], className)

  return <button ref={ref} className={classes} type={type} {...props} />
}

export default forwardRef<HTMLButtonElement, ButtonProps>(Button)
