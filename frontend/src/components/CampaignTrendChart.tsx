import type { CampaignTrendPoint } from '../features/dashboard/store/useDashboardStore'
import StatusMessage from './ui/StatusMessage'

import styles from './CampaignTrendChart.module.css'

interface CampaignTrendChartProps {
  data: CampaignTrendPoint[]
  currency: string
}

const svgHeight = 180
const svgWidth = 520

const CampaignTrendChart = ({ data, currency }: CampaignTrendChartProps) => {
  if (!data.length) {
    return (
      <StatusMessage variant="muted">
        Trend data will appear once we have daily results.
      </StatusMessage>
    )
  }

  const maxValue = Math.max(...data.map((point) => point.spend))
  const minValue = 0
  const yRange = maxValue - minValue || 1
  const xStep = svgWidth / Math.max(data.length - 1, 1)
  const currencyFormatter = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  })

  const linePath = data
    .map((point, index) => {
      const x = index * xStep
      const y = svgHeight - ((point.spend - minValue) / yRange) * svgHeight
      return `${index === 0 ? 'M' : 'L'}${x},${y}`
    })
    .join(' ')

  const areaPath = `${linePath} L${(data.length - 1) * xStep},${svgHeight} L0,${svgHeight} Z`

  return (
    <div className={styles.chart} role="img" aria-label="Campaign spend trend">
      <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} preserveAspectRatio="none">
        <path d={areaPath} className={styles.area} />
        <path d={linePath} className={styles.line} />
        {data.map((point, index) => {
          const x = index * xStep
          const y = svgHeight - ((point.spend - minValue) / yRange) * svgHeight
          return <circle key={point.date} cx={x} cy={y} r={3} className={styles.point} />
        })}
      </svg>
      <div className={styles.footer}>
        <div>
          <strong>{currencyFormatter.format(maxValue)}</strong>
          <span> peak daily spend</span>
        </div>
        <div className={styles.dates}>
          <span>{new Date(data[0].date).toLocaleDateString()}</span>
          <span>{new Date(data[data.length - 1].date).toLocaleDateString()}</span>
        </div>
      </div>
    </div>
  )
}

export default CampaignTrendChart
