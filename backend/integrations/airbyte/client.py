"""Thin HTTP client for interacting with the Airbyte OSS API."""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class AirbyteClientError(RuntimeError):
    """Raised when the Airbyte API responds with an error."""


class AirbyteClientConfigurationError(RuntimeError):
    """Raised when the client cannot be constructed from settings."""


@dataclass
class AirbyteClient:
    """Simple wrapper around the Airbyte HTTP API."""

    base_url: str
    token: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    timeout: float = 30.0

    def __post_init__(self) -> None:
        if not self.base_url:
            raise AirbyteClientConfigurationError("Airbyte base URL is required")
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        elif self.username and self.password:
            credentials = f"{self.username}:{self.password}".encode()
            headers["Authorization"] = "Basic " + base64.b64encode(credentials).decode()
        self._client = httpx.Client(base_url=self.base_url.rstrip("/"), headers=headers, timeout=self.timeout)

    def __enter__(self) -> "AirbyteClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001, ANN204
        self.close()

    def close(self) -> None:
        self._client.close()

    @classmethod
    def from_settings(cls) -> "AirbyteClient":
        base_url = getattr(settings, "AIRBYTE_API_URL", None)
        token = getattr(settings, "AIRBYTE_API_TOKEN", None)
        username = getattr(settings, "AIRBYTE_USERNAME", None)
        password = getattr(settings, "AIRBYTE_PASSWORD", None)
        if not base_url:
            raise AirbyteClientConfigurationError("AIRBYTE_API_URL must be configured")
        if not token and not (username and password):
            raise AirbyteClientConfigurationError(
                "Configure AIRBYTE_API_TOKEN or the AIRBYTE_USERNAME/AIRBYTE_PASSWORD pair"
            )
        return cls(base_url=base_url, token=token, username=username, password=password)

    def trigger_sync(self, connection_id: str) -> Dict[str, Any]:
        """Start a sync job for the given connection."""

        try:
            response = self._client.post("/api/v1/connections/sync", json={"connectionId": connection_id})
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - httpx provides detail
            raise AirbyteClientError(f"Failed to trigger sync for {connection_id}: {exc}") from exc
        payload = response.json()
        logger.debug("Triggered Airbyte sync", extra={"connection_id": connection_id, "response": payload})
        return payload

    def get_job(self, job_id: int) -> Dict[str, Any]:
        """Retrieve a job by identifier."""

        try:
            response = self._client.post("/api/v1/jobs/get", json={"id": job_id})
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - httpx provides detail
            raise AirbyteClientError(f"Failed to fetch job {job_id}: {exc}") from exc
        payload = response.json()
        logger.debug("Fetched Airbyte job", extra={"job_id": job_id, "response": payload})
        return payload

    def latest_job(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Return the most recent job for the connection, if available."""

        try:
            response = self._client.post(
                "/api/v1/jobs/list",
                json={
                    "configTypes": ["sync"],
                    "connectionId": connection_id,
                    "pagination": {"pageSize": 1},
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - httpx provides detail
            raise AirbyteClientError(f"Failed to list jobs for {connection_id}: {exc}") from exc
        payload: Dict[str, Any] = response.json()
        jobs = payload.get("jobs", [])
        return jobs[0] if jobs else None

