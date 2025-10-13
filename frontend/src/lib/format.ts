const integerFormatter = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })

export function formatNumber(value: number | undefined | null): string {
  return integerFormatter.format(Number.isFinite(Number(value)) ? Number(value) : 0)
}

export function formatCurrency(
  value: number | undefined | null,
  currency = 'USD',
  maximumFractionDigits = 0,
): string {
  const formatter = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    maximumFractionDigits,
  })
  return formatter.format(Number.isFinite(Number(value)) ? Number(value) : 0)
}

export function formatPercent(value: number | undefined | null, maximumFractionDigits = 1): string {
  const formatter = new Intl.NumberFormat('en-US', {
    style: 'percent',
    maximumFractionDigits,
  })
  return formatter.format(Number.isFinite(Number(value)) ? Number(value) : 0)
}

export function formatRatio(value: number | undefined | null, digits = 2): string {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return (0).toFixed(digits)
  }
  return numeric.toFixed(digits)
}
