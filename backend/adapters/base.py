"""Abstract interfaces for analytics adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class AdapterInterface:
    """Describe a surface area that an adapter can satisfy."""

    key: str
    label: str
    description: str | None = None


DEFAULT_INTERFACES: tuple[AdapterInterface, ...] = (
    AdapterInterface(key="meta", label="Meta Ads"),
    AdapterInterface(key="google_ads", label="Google Ads"),
    AdapterInterface(key="tiktok", label="TikTok"),
)


def get_default_interfaces() -> tuple[AdapterInterface, ...]:
    """Return a tuple of the standard advertising interfaces."""

    return DEFAULT_INTERFACES


class MetricsAdapter(ABC):
    """Base class for pluggable metrics providers."""

    #: Unique identifier used in API requests.
    key: str
    #: Human-friendly display name for UI menus.
    name: str
    #: Optional description shown in adapter pickers.
    description: str | None = None
    #: Interfaces that this adapter can satisfy.
    interfaces: Sequence[AdapterInterface] = ()

    def metadata(self) -> dict[str, Any]:
        """Return serialisable metadata for the adapter."""

        return {
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "interfaces": [
                {
                    "key": interface.key,
                    "label": interface.label,
                    "description": interface.description,
                }
                for interface in self.interfaces
            ],
        }

    @abstractmethod
    def fetch_metrics(
        self,
        *,
        tenant_id: str,
        options: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        """Collect metrics payloads for the requested tenant."""

        raise NotImplementedError
