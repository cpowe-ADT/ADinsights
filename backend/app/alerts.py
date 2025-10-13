"""Alert rule definitions and execution helpers."""

from dataclasses import dataclass
from typing import Any, Dict, Iterable

from django.db import connection


@dataclass(frozen=True)
class AlertRule:
    """Represents a SQL alert evaluated against the analytics warehouse."""

    slug: str
    name: str
    description: str
    severity: str
    sql: str
    max_rows: int = 25


def _strip_sql(sql: str) -> str:
    return "\n".join(line.rstrip() for line in sql.strip().splitlines())


ALERT_RULES: tuple[AlertRule, ...] = (
    AlertRule(
        slug="campaign_ctr_drop",
        name="Campaign CTR regression",
        description=(
            "Flags campaigns whose latest click-through rate is more than 50% below "
            "their trailing 7-day average while still spending meaningful budget."
        ),
        severity="high",
        sql=_strip_sql(
            """
            with ranked as (
                select
                    date_day,
                    source_platform,
                    ad_account_id,
                    campaign_id,
                    parish_name,
                    spend,
                    ctr,
                    avg(ctr) over (
                        partition by source_platform, ad_account_id, campaign_id
                        order by date_day
                        rows between 7 preceding and 1 preceding
                    ) as trailing_ctr,
                    row_number() over (
                        partition by source_platform, ad_account_id, campaign_id
                        order by date_day desc
                    ) as recency_rank
                from vw_campaign_daily
            )
            select
                date_day,
                source_platform,
                ad_account_id,
                campaign_id,
                parish_name,
                spend,
                ctr,
                trailing_ctr,
                case
                    when trailing_ctr > 0 then ctr / nullif(trailing_ctr, 0)
                end as ctr_vs_trailing
            from ranked
            where recency_rank = 1
              and trailing_ctr is not null
              and trailing_ctr > 0.0005
              and ctr < trailing_ctr * 0.5
              and spend >= 50
            order by ctr_vs_trailing asc nulls last
            limit %(limit)s
            """
        ),
    ),
    AlertRule(
        slug="account_spend_spike",
        name="Account spend spike",
        description=(
            "Highlights accounts whose most recent spend is materially higher than "
            "their trailing seven day average, indicating pacing risk."
        ),
        severity="medium",
        sql=_strip_sql(
            """
            with windowed as (
                select
                    date_day,
                    source_platform,
                    ad_account_id,
                    spend,
                    trailing_7d_avg_spend,
                    row_number() over (
                        partition by source_platform, ad_account_id
                        order by date_day desc
                    ) as recency_rank
                from vw_pacing
            )
            select
                date_day,
                source_platform,
                ad_account_id,
                spend,
                trailing_7d_avg_spend,
                spend - trailing_7d_avg_spend as spend_variance,
                case
                    when trailing_7d_avg_spend > 0 then spend / nullif(trailing_7d_avg_spend, 0)
                end as spend_vs_avg
            from windowed
            where recency_rank = 1
              and trailing_7d_avg_spend is not null
              and spend > trailing_7d_avg_spend * 1.4
              and spend >= 200
            order by spend_vs_avg desc nulls last
            limit %(limit)s
            """
        ),
    ),
    AlertRule(
        slug="creative_cpm_outlier",
        name="Creative CPM outlier",
        description=(
            "Surfaces creatives whose CPM materially exceeds their trailing 7-day "
            "trend while still gathering statistically significant impressions."
        ),
        severity="medium",
        sql=_strip_sql(
            """
            with ranked as (
                select
                    date_day,
                    source_platform,
                    ad_account_id,
                    ad_id,
                    adset_id,
                    campaign_id,
                    impressions,
                    spend,
                    cpm,
                    avg(cpm) over (
                        partition by source_platform, ad_account_id, ad_id
                        order by date_day
                        rows between 7 preceding and 1 preceding
                    ) as trailing_cpm,
                    row_number() over (
                        partition by source_platform, ad_account_id, ad_id
                        order by date_day desc
                    ) as recency_rank
                from vw_creative_daily
            )
            select
                date_day,
                source_platform,
                ad_account_id,
                ad_id,
                adset_id,
                campaign_id,
                impressions,
                spend,
                cpm,
                trailing_cpm,
                cpm - trailing_cpm as cpm_variance
            from ranked
            where recency_rank = 1
              and trailing_cpm is not null
              and trailing_cpm > 0
              and impressions >= 1000
              and spend >= 20
              and cpm > trailing_cpm * 1.4
            order by cpm_variance desc nulls last
            limit %(limit)s
            """
        ),
    ),
)


_RULE_INDEX = {rule.slug: rule for rule in ALERT_RULES}


def get_rule(slug: str) -> AlertRule:
    try:
        return _RULE_INDEX[slug]
    except KeyError as exc:  # pragma: no cover - defensive branch
        raise ValueError(f"Unknown alert rule '{slug}'") from exc


class AlertEvaluator:
    """Executes alert SQL rules and returns structured rows."""

    def __init__(self, django_connection=connection) -> None:
        self._connection = django_connection

    def run(self, rule: AlertRule) -> list[Dict[str, Any]]:
        with self._connection.cursor() as cursor:
            cursor.execute(rule.sql, {"limit": rule.max_rows})
            columns = [meta[0] for meta in cursor.description or ()]
            rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]


def iter_rules() -> Iterable[AlertRule]:
    return iter(ALERT_RULES)


__all__ = ["AlertRule", "ALERT_RULES", "AlertEvaluator", "get_rule", "iter_rules"]
