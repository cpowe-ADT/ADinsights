import CreativeTable from '../components/CreativeTable'
import FullPageLoader from '../components/FullPageLoader'
import DashboardShell, { DashboardPanel } from '../components/layout/DashboardShell'
import StatusMessage from '../components/ui/StatusMessage'
import useDashboardStore from '../features/dashboard/store/useDashboardStore'

const CreativeDashboard = () => {
  const { creative, campaign, creativeRows } = useDashboardStore((state) => ({
    creative: state.creative,
    campaign: state.campaign,
    creativeRows: state.getCreativeRowsForSelectedParish(),
  }))

  const currency = campaign.data?.summary.currency ?? 'USD'

  if (creative.status === 'loading' && !creative.data) {
    return <FullPageLoader message="Loading creative performance…" />
  }

  if (creative.status === 'error' && !creative.data) {
    return (
      <StatusMessage variant="error">
        {creative.error ?? 'Unable to load creative performance.'}
      </StatusMessage>
    )
  }

  if (!creative.data) {
    return (
      <StatusMessage variant="muted">
        Creative insights will appear once ads accrue spend.
      </StatusMessage>
    )
  }

  return (
    <DashboardShell layout="single">
      <DashboardPanel fullWidth>
        <CreativeTable rows={creativeRows} currency={currency} />
      </DashboardPanel>
    </DashboardShell>
  )
}

export default CreativeDashboard
