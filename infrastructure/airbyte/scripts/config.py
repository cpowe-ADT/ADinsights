"""Utilities for loading Airbyte environment-driven configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Dict, List, Optional

# Supported time units for Airbyte basic schedules
_VALID_TIME_UNITS = {"minutes", "hours", "days"}


def _slug_to_env_prefix(slug: str) -> str:
    return slug.strip().upper().replace("-", "_").replace(" ", "_")


def _slug_to_display_name(slug: str) -> str:
    parts = slug.replace("-", " ").replace("_", " ").split()
    return " ".join(word.capitalize() for word in parts) if parts else slug


@dataclass(frozen=True)
class ScheduleDefaults:
    cron: str
    timezone: str
    basic_units: int
    basic_time_unit: str


@dataclass(frozen=True)
class ConnectionTemplate:
    key: str
    display_name: str
    template_env: str
    schedule_group: str
    defaults: ScheduleDefaults


# Connection template order ensures deterministic bootstrap behavior.
TEMPLATE_ORDER: List[ConnectionTemplate] = [
    ConnectionTemplate(
        key="meta_metrics",
        display_name="Meta Marketing Metrics",
        template_env="AIRBYTE_TEMPLATE_META_METRICS_CONNECTION_ID",
        schedule_group="METRICS",
        defaults=ScheduleDefaults(
            cron="0 6-22 * * *",
            timezone="America/Jamaica",
            basic_units=1,
            basic_time_unit="hours",
        ),
    ),
    ConnectionTemplate(
        key="google_metrics",
        display_name="Google Ads Metrics",
        template_env="AIRBYTE_TEMPLATE_GOOGLE_METRICS_CONNECTION_ID",
        schedule_group="METRICS",
        defaults=ScheduleDefaults(
            cron="0 6-22 * * *",
            timezone="America/Jamaica",
            basic_units=1,
            basic_time_unit="hours",
        ),
    ),
    ConnectionTemplate(
        key="dimensions_daily",
        display_name="Dimensions Daily",
        template_env="AIRBYTE_TEMPLATE_DIMENSIONS_DAILY_CONNECTION_ID",
        schedule_group="DAILY",
        defaults=ScheduleDefaults(
            cron="15 2 * * *",
            timezone="America/Jamaica",
            basic_units=1,
            basic_time_unit="days",
        ),
    ),
]
TEMPLATE_INDEX: Dict[str, ConnectionTemplate] = {t.key: t for t in TEMPLATE_ORDER}


@dataclass
class ScheduleConfig:
    cron_expression: Optional[str]
    cron_timezone: Optional[str]
    basic_units: int
    basic_time_unit: str

    def validate(self, label: str) -> List[str]:
        errors: List[str] = []
        if self.cron_expression:
            if not _looks_like_cron(self.cron_expression):
                errors.append(f"{label}: cron expression '{self.cron_expression}' is invalid")
            if not self.cron_timezone:
                errors.append(f"{label}: cron timezone is required when using cron scheduling")
        else:
            if self.basic_units <= 0:
                errors.append(f"{label}: basic schedule units must be > 0")
            if self.basic_time_unit not in _VALID_TIME_UNITS:
                errors.append(
                    f"{label}: basic schedule time unit must be one of {_VALID_TIME_UNITS}, "
                    f"got '{self.basic_time_unit}'"
                )
        return errors

    def to_airbyte_payload(self) -> (str, Dict[str, Dict[str, object]]):
        if self.cron_expression:
            return (
                "cron",
                {
                    "cron": {
                        "cronExpression": self.cron_expression,
                        "cronTimeZone": self.cron_timezone,
                    }
                },
            )
        return (
            "basic",
            {
                "basicSchedule": {
                    "timeUnit": self.basic_time_unit,
                    "units": int(self.basic_units),
                }
            },
        )

    @property
    def expected_interval_seconds(self) -> Optional[int]:
        if self.cron_expression:
            return None
        multipliers = {"minutes": 60, "hours": 3600, "days": 86400}
        return int(self.basic_units) * multipliers[self.basic_time_unit]


@dataclass
class TenantConnectionConfig:
    name: str
    status: str
    schedule: ScheduleConfig
    prefix: Optional[str]
    existing_connection_id: Optional[str] = None


@dataclass
class TenantConfig:
    slug: str
    display_name: str
    workspace_id: str
    destination_id: str
    namespace: Optional[str]
    bucket: Optional[str]
    stream_prefix: Optional[str]
    connections: Dict[str, TenantConnectionConfig] = field(default_factory=dict)

    @property
    def env_prefix(self) -> str:
        return _slug_to_env_prefix(self.slug)

    def connection(self, key: str) -> TenantConnectionConfig:
        return self.connections[key]


@dataclass
class AirbyteEnvironment:
    base_url: str
    auth_header: Optional[str]
    default_timezone: Optional[str]
    templates: Dict[str, str]
    tenants: List[TenantConfig]

    def template_connection_id(self, key: str) -> str:
        return self.templates[key]


def _looks_like_cron(expression: str) -> bool:
    parts = [part for part in expression.strip().split() if part]
    return 5 <= len(parts) <= 6


def _read_env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    if value == "":
        return default
    return value


def load_environment() -> AirbyteEnvironment:
    base_url = os.getenv("AIRBYTE_BASE_URL", "http://localhost:8001")
    auth_header = _read_env("AIRBYTE_API_AUTH_HEADER")
    default_timezone = _read_env("AIRBYTE_DEFAULT_TIMEZONE", "America/Jamaica")

    templates: Dict[str, str] = {}
    for template in TEMPLATE_ORDER:
        connection_id = _read_env(template.template_env)
        if not connection_id:
            raise ValueError(f"{template.template_env} is required to bootstrap connections")
        templates[template.key] = connection_id

    tenant_slugs = [slug.strip() for slug in os.getenv("AIRBYTE_TENANTS", "").split(",") if slug.strip()]
    if not tenant_slugs:
        raise ValueError("AIRBYTE_TENANTS must contain at least one tenant slug")

    default_namespace = _read_env("AIRBYTE_DEFAULT_DESTINATION_NAMESPACE")
    default_bucket = _read_env("AIRBYTE_DEFAULT_DESTINATION_BUCKET")
    default_prefix = _read_env("AIRBYTE_DEFAULT_STREAM_PREFIX", "")

    tenants: List[TenantConfig] = []
    for slug in tenant_slugs:
        env_prefix = _slug_to_env_prefix(slug)
        display_name = _read_env(f"AIRBYTE_{env_prefix}_DISPLAY_NAME", _slug_to_display_name(slug))
        workspace_id = _read_env(f"AIRBYTE_{env_prefix}_WORKSPACE_ID")
        destination_id = _read_env(f"AIRBYTE_{env_prefix}_DESTINATION_ID")
        if not workspace_id:
            raise ValueError(f"AIRBYTE_{env_prefix}_WORKSPACE_ID is required")
        if not destination_id:
            raise ValueError(f"AIRBYTE_{env_prefix}_DESTINATION_ID is required")
        namespace = _read_env(f"AIRBYTE_{env_prefix}_DESTINATION_NAMESPACE", default_namespace)
        bucket = _read_env(f"AIRBYTE_{env_prefix}_DESTINATION_BUCKET", default_bucket)
        stream_prefix = _read_env(f"AIRBYTE_{env_prefix}_STREAM_PREFIX", default_prefix)

        connection_configs: Dict[str, TenantConnectionConfig] = {}
        for template in TEMPLATE_ORDER:
            key_upper = template.key.upper()
            schedule = _resolve_schedule(env_prefix, template)
            status = (_read_env(f"AIRBYTE_{env_prefix}_{key_upper}_STATUS", "active") or "active").lower()
            if status not in {"active", "inactive"}:
                raise ValueError(
                    f"AIRBYTE_{env_prefix}_{key_upper}_STATUS must be 'active' or 'inactive', got '{status}'"
                )
            name = _read_env(
                f"AIRBYTE_{env_prefix}_{key_upper}_NAME",
                f"{display_name} {template.display_name}",
            )
            prefix_override = _read_env(f"AIRBYTE_{env_prefix}_{key_upper}_PREFIX")
            existing_id = _read_env(f"AIRBYTE_{env_prefix}_{key_upper}_CONNECTION_ID")
            connection_configs[template.key] = TenantConnectionConfig(
                name=name,
                status=status,
                schedule=schedule,
                prefix=prefix_override if prefix_override is not None else stream_prefix,
                existing_connection_id=existing_id,
            )
        tenants.append(
            TenantConfig(
                slug=slug,
                display_name=display_name or slug,
                workspace_id=workspace_id,
                destination_id=destination_id,
                namespace=namespace,
                bucket=bucket,
                stream_prefix=stream_prefix,
                connections=connection_configs,
            )
        )

    return AirbyteEnvironment(
        base_url=base_url,
        auth_header=auth_header,
        default_timezone=default_timezone,
        templates=templates,
        tenants=tenants,
    )


def _resolve_schedule(env_prefix: str, template: ConnectionTemplate) -> ScheduleConfig:
    group = template.schedule_group
    cron = _read_env(f"AIRBYTE_{env_prefix}_{group}_CRON")
    if cron is None:
        cron = _read_env(f"AIRBYTE_DEFAULT_{group}_CRON", template.defaults.cron)
    timezone = _read_env(f"AIRBYTE_{env_prefix}_{group}_TIMEZONE")
    if timezone is None:
        timezone = _read_env(f"AIRBYTE_DEFAULT_{group}_TIMEZONE", template.defaults.timezone)
    basic_units_value = _read_env(f"AIRBYTE_{env_prefix}_{group}_BASIC_UNITS")
    if basic_units_value is None:
        basic_units_value = _read_env(
            f"AIRBYTE_DEFAULT_{group}_BASIC_UNITS",
            str(template.defaults.basic_units),
        )
    basic_time_unit = _read_env(f"AIRBYTE_{env_prefix}_{group}_BASIC_TIME_UNIT")
    if basic_time_unit is None:
        basic_time_unit = _read_env(
            f"AIRBYTE_DEFAULT_{group}_BASIC_TIME_UNIT",
            template.defaults.basic_time_unit,
        )
    try:
        basic_units = int(basic_units_value)
    except (TypeError, ValueError):
        raise ValueError(
            f"AIRBYTE_{env_prefix}_{group}_BASIC_UNITS must be an integer, got '{basic_units_value}'"
        )

    cron_expression = cron if cron not in {None, ""} else None
    cron_timezone = timezone if cron_expression else None
    return ScheduleConfig(
        cron_expression=cron_expression,
        cron_timezone=cron_timezone,
        basic_units=basic_units,
        basic_time_unit=(basic_time_unit or template.defaults.basic_time_unit).lower(),
    )


__all__ = [
    "AirbyteEnvironment",
    "ScheduleConfig",
    "TenantConfig",
    "TenantConnectionConfig",
    "TEMPLATE_ORDER",
    "load_environment",
    "_looks_like_cron",
]
