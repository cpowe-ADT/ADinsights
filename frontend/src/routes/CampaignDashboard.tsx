import CampaignTable from '../components/CampaignTable'
import CampaignTrendChart from '../components/CampaignTrendChart'
import FullPageLoader from '../components/FullPageLoader'
import KpiCard from '../components/KpiCard'
import DashboardShell, { DashboardPanel } from '../components/layout/DashboardShell'
import ParishMap from '../components/ParishMap'
import StatusMessage from '../components/ui/StatusMessage'
import useDashboardStore from '../features/dashboard/store/useDashboardStore'
import { formatCurrency, formatNumber, formatRatio } from '../lib/format'

import styles from './CampaignDashboard.module.css'

const CampaignDashboard = () => {
  const { campaign, campaignRows } = useDashboardStore((state) => ({
    campaign: state.campaign,
    campaignRows: state.getCampaignRowsForSelectedParish(),
  }))

  if (campaign.status === 'loading' && !campaign.data) {
    return <FullPageLoader message="Loading campaign performance…" />
  }

  if (campaign.status === 'error' && !campaign.data) {
    return (
      <StatusMessage variant="error">
        {campaign.error ?? 'Unable to load campaign performance.'}
      </StatusMessage>
    )
  }

  if (!campaign.data) {
    return (
      <StatusMessage variant="muted">
        Campaign performance will appear once metrics are ingested.
      </StatusMessage>
    )
  }

  const { summary, trend } = campaign.data
  const currency = summary.currency ?? 'USD'

  const kpis = [
    { label: 'Spend', value: formatCurrency(summary.totalSpend, currency) },
    { label: 'Impressions', value: formatNumber(summary.totalImpressions) },
    { label: 'Clicks', value: formatNumber(summary.totalClicks) },
    { label: 'Conversions', value: formatNumber(summary.totalConversions) },
    { label: 'Avg. ROAS', value: formatRatio(summary.averageRoas, 2) },
  ]

  return (
    <DashboardShell>
      <DashboardPanel fullWidth>
        <section className={styles.kpiGrid} aria-label="Campaign KPIs">
          {kpis.map((kpi) => (
            <KpiCard key={kpi.label} label={kpi.label} value={kpi.value} />
          ))}
        </section>
      </DashboardPanel>
      <DashboardPanel>
        <header className={styles.panelHeader}>
          <h2 className={styles.panelTitle}>Daily spend trend</h2>
        </header>
        <CampaignTrendChart data={trend} currency={currency} />
      </DashboardPanel>
      <DashboardPanel className={styles.mapPanel}>
        <header className={styles.panelHeader}>
          <h2 className={styles.panelTitle}>Parish heatmap</h2>
          <p className={styles.panelDescription}>
            Click a parish to filter the performance tables below.
          </p>
        </header>
        <ParishMap />
      </DashboardPanel>
      <DashboardPanel fullWidth>
        <CampaignTable rows={campaignRows} currency={currency} />
      </DashboardPanel>
    </DashboardShell>
  )
}

export default CampaignDashboard
