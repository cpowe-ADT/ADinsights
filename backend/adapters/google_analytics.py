from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Mapping

from django.utils import timezone
from integrations.models import GoogleAnalyticsConnection
from integrations.google_analytics.client import GoogleAnalyticsClient
from .base import AdapterInterface, MetricsAdapter

logger = logging.getLogger(__name__)


class GoogleAnalyticsAdapter(MetricsAdapter):
    key = "google_analytics"
    name = "Google Analytics 4"
    description = "Web traffic and engagement data from GA4."
    interfaces = (
        AdapterInterface(key="google_analytics", label="Google Analytics"),
    )

    def fetch_metrics(
        self,
        *,
        tenant_id: str,
        options: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        options = options or {}
        end_date = options.get("end_date") or timezone.now().date()
        if isinstance(end_date, str):
            end_date = date.fromisoformat(end_date)
        
        start_date = options.get("start_date") or (end_date - timedelta(days=30))
        if isinstance(start_date, str):
            start_date = date.fromisoformat(start_date)

        connection = GoogleAnalyticsConnection.objects.filter(
            tenant_id=tenant_id, is_active=True
        ).order_by("-updated_at", "-created_at").first()

        if not connection:
            return {
                "summary": {
                    "sessions": 0,
                    "users": 0,
                    "new_users": 0,
                    "engagement_rate": 0.0,
                    "average_session_duration": 0.0,
                    "conversions": 0,
                    "event_count": 0,
                },
                "rows": [],
            }

        client = GoogleAnalyticsClient(credential=connection.credentials)
        try:
            ga_rows = client.fetch_traffic_acquisition(
                property_id=connection.property_id,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as exc:
            logger.error("Failed to fetch GA4 metrics for tenant %s", tenant_id, exc_info=exc)
            return {
                "summary": {"error": str(exc)},
                "rows": [],
            }

        rows = []
        total_sessions = 0
        total_users = 0
        total_new_users = 0
        total_conversions = 0
        total_event_count = 0
        weighted_engagement_rate = 0.0
        weighted_session_duration = 0.0

        for row in ga_rows:
            total_sessions += row.sessions
            total_users += row.users
            total_new_users += row.new_users
            total_conversions += row.conversions
            total_event_count += row.event_count
            weighted_engagement_rate += row.engagement_rate * row.sessions
            weighted_session_duration += row.average_session_duration * row.sessions

            rows.append(
                {
                    "date": row.date_day.isoformat(),
                    "source": row.source,
                    "medium": row.medium,
                    "campaign": row.campaign,
                    "sessions": row.sessions,
                    "users": row.users,
                    "new_users": row.new_users,
                    "engagement_rate": row.engagement_rate,
                    "average_session_duration": row.average_session_duration,
                    "conversions": row.conversions,
                    "event_count": row.event_count,
                }
            )

        avg_engagement_rate = weighted_engagement_rate / total_sessions if total_sessions else 0.0
        avg_session_duration = weighted_session_duration / total_sessions if total_sessions else 0.0

        return {
            "summary": {
                "sessions": total_sessions,
                "users": total_users,
                "new_users": total_new_users,
                "engagement_rate": avg_engagement_rate,
                "average_session_duration": avg_session_duration,
                "conversions": total_conversions,
                "event_count": total_event_count,
            },
            "rows": rows,
        }
