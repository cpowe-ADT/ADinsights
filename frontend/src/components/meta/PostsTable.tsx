import { formatNumber } from '../../lib/format';
import type { MetaPostListItem } from '../../lib/metaPageInsights';

type PostsTableProps = {
  rows: MetaPostListItem[];
  onSelectPost: (postId: string) => void;
  selectedPostId: string;
};

const PostsTable = ({ rows, onSelectPost, selectedPostId }: PostsTableProps) => {
  return (
    <article className="panel">
      <h3>Posts</h3>
      <div className="table-responsive">
        <table className="dashboard-table">
          <thead>
            <tr className="dashboard-table__header-row">
              <th className="dashboard-table__header-cell">Post ID</th>
              <th className="dashboard-table__header-cell">Created</th>
              <th className="dashboard-table__header-cell">Message</th>
              <th className="dashboard-table__header-cell">Like Reactions</th>
              <th className="dashboard-table__header-cell">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.post_id}
                className={`dashboard-table__row dashboard-table__row--zebra ${
                  selectedPostId === row.post_id ? 'meta-post-row--selected' : ''
                }`}
              >
                <td className="dashboard-table__cell">{row.post_id}</td>
                <td className="dashboard-table__cell">{row.created_time ? row.created_time.slice(0, 10) : '—'}</td>
                <td className="dashboard-table__cell">{row.message || '—'}</td>
                <td className="dashboard-table__cell">
                  {typeof row.metrics.post_reactions_like_total === 'number' ||
                  typeof row.metrics.post_reactions_like_total === 'string'
                    ? formatNumber(Number(row.metrics.post_reactions_like_total))
                    : '—'}
                </td>
                <td className="dashboard-table__cell">
                  <button className="button tertiary" type="button" onClick={() => onSelectPost(row.post_id)}>
                    Drill down
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </article>
  );
};

export default PostsTable;
