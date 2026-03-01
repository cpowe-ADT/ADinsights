"""Phase 2 web analytics API endpoints (GA4 + Search Console)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from django.db import connection
from django.utils.dateparse import parse_date
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


@dataclass(frozen=True)
class WebSourceConfig:
    key: str
    table: str
    date_column: str
    dimensions: tuple[str, ...]
    metrics: tuple[str, ...]


GA4_CONFIG = WebSourceConfig(
    key="ga4",
    table="agg_ga4_daily",
    date_column="date_day",
    dimensions=("property_id", "channel_group", "country", "city", "campaign_name"),
    metrics=(
        "sessions",
        "engaged_sessions",
        "conversions",
        "purchase_revenue",
        "engagement_rate",
        "conversion_rate",
    ),
)

SEARCH_CONSOLE_CONFIG = WebSourceConfig(
    key="search_console",
    table="agg_search_console_daily",
    date_column="date_day",
    dimensions=("site_url", "country", "device", "query", "page"),
    metrics=("clicks", "impressions", "ctr", "position"),
)


class BaseWebSourceView(APIView):
    permission_classes = [IsAuthenticated]
    source_config: WebSourceConfig | None = None

    def get(self, request) -> Response:  # noqa: D401
        if self.source_config is None:
            return Response({"detail": "Source config missing."}, status=500)

        start_date = self._parse_date(request.query_params.get("start_date"))
        end_date = self._parse_date(request.query_params.get("end_date"))
        if start_date and end_date and start_date > end_date:
            return Response(
                {"detail": "start_date must be before or equal to end_date."},
                status=400,
            )

        payload = self._load_rows(
            tenant_id=str(request.user.tenant_id),
            config=self.source_config,
            start_date=start_date,
            end_date=end_date,
        )
        return Response(payload)

    def _parse_date(self, raw: str | None) -> date | None:
        if not raw:
            return None
        return parse_date(raw)

    def _load_rows(
        self,
        *,
        tenant_id: str,
        config: WebSourceConfig,
        start_date: date | None,
        end_date: date | None,
    ) -> dict[str, Any]:
        columns = ["tenant_id", config.date_column, *config.dimensions, *config.metrics]
        where = ["tenant_id = %s"]
        params: list[Any] = [tenant_id]

        if start_date is not None:
            where.append(f"{config.date_column} >= %s")
            params.append(start_date)
        if end_date is not None:
            where.append(f"{config.date_column} <= %s")
            params.append(end_date)

        where_sql = " AND ".join(where)
        columns_sql = ", ".join(columns)
        query = (
            f"SELECT {columns_sql} FROM {config.table} "
            f"WHERE {where_sql} ORDER BY {config.date_column} DESC LIMIT 500"
        )

        try:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                records = cursor.fetchall()
                names = [col[0] for col in cursor.description]
        except Exception as exc:  # pragma: no cover - defensive fallback
            return {
                "source": config.key,
                "status": "unavailable",
                "detail": str(exc),
                "rows": [],
            }

        rows = [dict(zip(names, row, strict=False)) for row in records]
        return {
            "source": config.key,
            "status": "ok",
            "count": len(rows),
            "rows": rows,
        }


class GA4WebInsightsView(BaseWebSourceView):
    source_config = GA4_CONFIG


class SearchConsoleInsightsView(BaseWebSourceView):
    source_config = SEARCH_CONSOLE_CONFIG
