type Props = {
  title: string;
  description?: string;
  status: 'idle' | 'loading' | 'success' | 'error';
  error: string;
  data: unknown;
  emptyMessage?: string;
};

function asRows(data: unknown): Record<string, unknown>[] {
  if (Array.isArray(data)) {
    return data.filter((row): row is Record<string, unknown> => Boolean(row) && typeof row === 'object');
  }
  if (data && typeof data === 'object') {
    const payload = data as { results?: unknown };
    if (Array.isArray(payload.results)) {
      return payload.results.filter(
        (row): row is Record<string, unknown> => Boolean(row) && typeof row === 'object',
      );
    }
  }
  return [];
}

function asSingleObject(data: unknown): Record<string, unknown> | null {
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    return null;
  }
  const payload = data as { results?: unknown };
  if (Array.isArray(payload.results)) {
    return null;
  }
  return data as Record<string, unknown>;
}

const GenericTabSection = ({
  title,
  description,
  status,
  error,
  data,
  emptyMessage = 'No results for the selected filters.',
}: Props) => {
  const rows = asRows(data);
  const objectPayload = asSingleObject(data);
  const columns = rows.length > 0 ? Object.keys(rows[0] ?? {}) : [];

  if (status === 'loading' && rows.length === 0 && !objectPayload) {
    return <div className="panel">Loading {title.toLowerCase()}...</div>;
  }
  if (status === 'error' && rows.length === 0 && !objectPayload) {
    return (
      <div className="panel" role="alert">
        {error}
      </div>
    );
  }

  return (
    <section className="panel">
      <h2>{title}</h2>
      {description ? <p className="dashboardSubtitle">{description}</p> : null}

      {objectPayload ? (
        <dl className="gads-workspace__keyvals" style={{ marginTop: '0.5rem' }}>
          {Object.entries(objectPayload).map(([key, value]) => {
            if (value && typeof value === 'object') {
              return null;
            }
            return (
              <div key={key} style={{ display: 'contents' }}>
                <dt>{key.replace(/_/g, ' ')}</dt>
                <dd>{String(value ?? '—')}</dd>
              </div>
            );
          })}
        </dl>
      ) : null}

      {rows.length === 0 && !objectPayload ? <p className="muted">{emptyMessage}</p> : null}

      {rows.length > 0 ? (
        <div className="table-responsive">
          <table className="dashboard-table">
            <thead>
              <tr className="dashboard-table__header-row">
                {columns.map((column) => (
                  <th key={column} className="dashboard-table__header-cell">
                    {column.replace(/_/g, ' ')}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={`${index}-${String(row.id ?? row.campaign_id ?? row.resource_name ?? '')}`} className="dashboard-table__row dashboard-table__row--zebra">
                  {columns.map((column) => (
                    <td key={column} className="dashboard-table__cell">
                      {String(row[column] ?? '—')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
};

export default GenericTabSection;
