type CampaignRow = {
  campaign_id?: string;
  campaign_name?: string;
  campaign_status?: string;
  channel_type?: string;
  spend?: number;
  clicks?: number;
  impressions?: number;
  conversions?: number;
  roas?: number;
  cpa?: number;
};

type Payload = {
  count?: number;
  results?: CampaignRow[];
};

type Props = {
  data: unknown;
  status: 'idle' | 'loading' | 'success' | 'error';
  error: string;
  drawerCampaignId: string;
  onOpenDrawer: (campaignId: string) => void;
  onCloseDrawer: () => void;
};

const CampaignsTabSection = ({
  data,
  status,
  error,
  drawerCampaignId,
  onOpenDrawer,
  onCloseDrawer,
}: Props) => {
  const payload = (data as Payload) ?? {};
  const rows = Array.isArray(payload.results) ? payload.results : [];

  if (status === 'loading' && rows.length === 0) {
    return <div className="panel">Loading campaigns...</div>;
  }
  if (status === 'error' && rows.length === 0) {
    return (
      <div className="panel" role="alert">
        {error}
      </div>
    );
  }

  const selected = rows.find((row) => String(row.campaign_id ?? '') === drawerCampaignId) ?? null;

  return (
    <div className="gads-workspace__tab-grid gads-workspace__tab-grid--with-drawer">
      <section className="panel">
        <h2>Campaign performance ({payload.count ?? rows.length})</h2>
        <div className="table-responsive">
          <table className="dashboard-table">
            <thead>
              <tr className="dashboard-table__header-row">
                <th className="dashboard-table__header-cell">Campaign</th>
                <th className="dashboard-table__header-cell">Status</th>
                <th className="dashboard-table__header-cell">Channel</th>
                <th className="dashboard-table__header-cell">Spend</th>
                <th className="dashboard-table__header-cell">Clicks</th>
                <th className="dashboard-table__header-cell">Impr</th>
                <th className="dashboard-table__header-cell">Conv</th>
                <th className="dashboard-table__header-cell">CPA</th>
                <th className="dashboard-table__header-cell">ROAS</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const campaignId = String(row.campaign_id ?? '');
                return (
                  <tr key={campaignId || row.campaign_name} className="dashboard-table__row dashboard-table__row--zebra">
                    <td className="dashboard-table__cell">
                      <button
                        type="button"
                        className="button tertiary"
                        onClick={() => onOpenDrawer(campaignId)}
                        disabled={!campaignId}
                        aria-label={`Open campaign details for ${row.campaign_name ?? campaignId}`}
                      >
                        {row.campaign_name ?? campaignId}
                      </button>
                    </td>
                    <td className="dashboard-table__cell">{row.campaign_status ?? '—'}</td>
                    <td className="dashboard-table__cell">{row.channel_type ?? '—'}</td>
                    <td className="dashboard-table__cell">{Number(row.spend ?? 0).toFixed(2)}</td>
                    <td className="dashboard-table__cell">{Number(row.clicks ?? 0).toFixed(0)}</td>
                    <td className="dashboard-table__cell">{Number(row.impressions ?? 0).toFixed(0)}</td>
                    <td className="dashboard-table__cell">{Number(row.conversions ?? 0).toFixed(2)}</td>
                    <td className="dashboard-table__cell">{Number(row.cpa ?? 0).toFixed(2)}</td>
                    <td className="dashboard-table__cell">{Number(row.roas ?? 0).toFixed(2)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <aside className="panel gads-workspace__drawer" aria-live="polite">
        <div className="gads-workspace__drawer-head">
          <h3>Campaign drilldown</h3>
          <button type="button" className="button tertiary" onClick={onCloseDrawer}>
            Close
          </button>
        </div>
        {!selected ? <p className="muted">Select a campaign row to inspect details.</p> : null}
        {selected ? (
          <dl className="gads-workspace__keyvals">
            <dt>Campaign</dt>
            <dd>{selected.campaign_name ?? selected.campaign_id ?? '—'}</dd>
            <dt>Status</dt>
            <dd>{selected.campaign_status ?? '—'}</dd>
            <dt>Spend</dt>
            <dd>{Number(selected.spend ?? 0).toFixed(2)}</dd>
            <dt>Clicks</dt>
            <dd>{Number(selected.clicks ?? 0).toFixed(0)}</dd>
            <dt>Impressions</dt>
            <dd>{Number(selected.impressions ?? 0).toFixed(0)}</dd>
            <dt>Conversions</dt>
            <dd>{Number(selected.conversions ?? 0).toFixed(2)}</dd>
            <dt>CPA</dt>
            <dd>{Number(selected.cpa ?? 0).toFixed(2)}</dd>
            <dt>ROAS</dt>
            <dd>{Number(selected.roas ?? 0).toFixed(2)}</dd>
          </dl>
        ) : null}
      </aside>
    </div>
  );
};

export default CampaignsTabSection;
