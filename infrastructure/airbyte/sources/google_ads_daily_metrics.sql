SELECT
  segments.date,
  customer.id,
  campaign.id,
  ad_group.id,
  metrics.cost_micros,
  metrics.impressions,
  metrics.clicks,
  metrics.conversions,
  segments.geo_target_region
FROM ad_group
WHERE segments.date BETWEEN '{{ runtime_from_date }}' AND '{{ runtime_to_date }}'
