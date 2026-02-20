from __future__ import annotations

from datetime import date
from typing import Any, Literal

from integrations.meta_graph import MetaGraphClient, MetaGraphClientError
from integrations.services.meta_graph_client import (
    MetaInsightsGraphClient,
    MetaInsightsGraphClientError,
)

ObjectType = Literal["page", "post"]


class MetaPageInsightsApiError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: int | None = None,
        error_subcode: int | None = None,
        retryable: bool = False,
        payload: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.error_subcode = error_subcode
        self.retryable = retryable
        self.payload = payload or {}


class MetaPageInsightsClient:
    def __init__(
        self,
        *,
        insights_client: MetaInsightsGraphClient | None = None,
        graph_client: MetaGraphClient | None = None,
    ) -> None:
        self._insights_client = insights_client
        self._graph_client = graph_client
        self._owns_insights = insights_client is None
        self._owns_graph = graph_client is None

    @classmethod
    def from_settings(cls) -> "MetaPageInsightsClient":
        return cls(
            insights_client=MetaInsightsGraphClient.from_settings(),
            graph_client=MetaGraphClient.from_settings(),
        )

    def __enter__(self) -> "MetaPageInsightsClient":
        if self._insights_client is None:
            self._insights_client = MetaInsightsGraphClient.from_settings()
            self._owns_insights = True
        if self._graph_client is None:
            self._graph_client = MetaGraphClient.from_settings()
            self._owns_graph = True
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        if self._owns_insights and self._insights_client is not None:
            self._insights_client.close()
        if self._owns_graph and self._graph_client is not None:
            self._graph_client.close()

    def fetch_pages_for_user(self, *, user_access_token: str):
        try:
            return self._require_graph().list_pages(user_access_token=user_access_token)
        except MetaGraphClientError as exc:
            raise MetaPageInsightsApiError(
                str(exc),
                status_code=exc.status_code,
                error_code=exc.error_code,
                error_subcode=exc.error_subcode,
                retryable=exc.retryable,
            ) from exc

    def fetch_posts(
        self,
        *,
        page_id: str,
        since: date,
        until: date,
        token: str,
    ) -> list[dict[str, Any]]:
        try:
            return self._require_insights().fetch_page_posts(
                page_id=page_id,
                since=since.isoformat(),
                until=until.isoformat(),
                token=token,
            )
        except MetaInsightsGraphClientError as exc:
            raise MetaPageInsightsApiError(
                str(exc),
                status_code=exc.status_code,
                error_code=exc.error_code,
                error_subcode=exc.error_subcode,
                retryable=exc.retryable,
                payload=exc.payload,
            ) from exc

    def fetch_insights(
        self,
        *,
        object_type: ObjectType,
        object_id: str,
        metrics: list[str],
        period: str,
        since: date,
        until: date,
        token: str,
    ) -> dict[str, Any]:
        try:
            if object_type == "page":
                return self._require_insights().fetch_page_insights(
                    page_id=object_id,
                    metrics=metrics,
                    period=period,
                    since=since.isoformat(),
                    until=until.isoformat(),
                    token=token,
                )
            return self._require_insights().fetch_post_insights(
                post_id=object_id,
                metrics=metrics,
                period=period,
                since=since.isoformat(),
                until=until.isoformat(),
                token=token,
            )
        except MetaInsightsGraphClientError as exc:
            raise MetaPageInsightsApiError(
                str(exc),
                status_code=exc.status_code,
                error_code=exc.error_code,
                error_subcode=exc.error_subcode,
                retryable=exc.retryable,
                payload=exc.payload,
            ) from exc

    def request_url(self, *, url: str, token: str) -> dict[str, Any]:
        try:
            return self._require_insights().request(
                "GET",
                url,
                params=None,
                token=token,
            )
        except MetaInsightsGraphClientError as exc:
            raise MetaPageInsightsApiError(
                str(exc),
                status_code=exc.status_code,
                error_code=exc.error_code,
                error_subcode=exc.error_subcode,
                retryable=exc.retryable,
                payload=exc.payload,
            ) from exc

    def _require_insights(self) -> MetaInsightsGraphClient:
        if self._insights_client is None:
            self._insights_client = MetaInsightsGraphClient.from_settings()
            self._owns_insights = True
        return self._insights_client

    def _require_graph(self) -> MetaGraphClient:
        if self._graph_client is None:
            self._graph_client = MetaGraphClient.from_settings()
            self._owns_graph = True
        return self._graph_client
