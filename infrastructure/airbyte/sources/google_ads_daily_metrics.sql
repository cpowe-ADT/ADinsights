SELECT
  segments.date                  AS date_day,
  customer.id                    AS customer_id,
  campaign.id                    AS campaign_id,
  campaign.name                  AS campaign_name,
  ad_group.id                    AS ad_group_id,
  ad_group_ad.ad.id              AS criterion_id,
  ad_group_ad.ad.name            AS ad_name,
  segments.device                AS device,
  segments.geo_target_region     AS geo_target_region,
  metrics.cost_micros            AS cost_micros,
  customer.currency_code         AS currency_code,
  metrics.impressions            AS impressions,
  metrics.clicks                 AS clicks,
  metrics.conversions            AS conversions,
  metrics.conversions_value      AS conversions_value
FROM ad_group_ad
WHERE segments.date BETWEEN '{{ runtime_from_date }}' AND '{{ runtime_to_date }}'
