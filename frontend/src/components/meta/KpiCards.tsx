import { formatNumber } from '../../lib/format';
import type { MetaOverviewCard } from '../../lib/metaPageInsights';

type KpiCardsProps = {
  cards: MetaOverviewCard[];
};

const KpiCards = ({ cards }: KpiCardsProps) => {
  return (
    <div className="meta-kpi-grid">
      {cards.map((card) => (
        <article key={card.metric_key} className="panel meta-kpi-card">
          <p className="meta-kpi-title">{card.metric_key}</p>
          <h3>{card.value_range ? formatNumber(Number(card.value_range)) : '—'}</h3>
          <p className="meta-kpi-subtitle">Today: {card.value_today ? formatNumber(Number(card.value_today)) : '—'}</p>
          {card.status === 'INVALID' || card.status === 'DEPRECATED' ? (
            <p className="meta-warning-text">
              {card.status.toLowerCase()}
              {card.replacement_metric_key ? `, replacement: ${card.replacement_metric_key}` : ''}
            </p>
          ) : null}
        </article>
      ))}
    </div>
  );
};

export default KpiCards;
