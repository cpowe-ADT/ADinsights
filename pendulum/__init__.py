from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional


@dataclass(frozen=True)
class _PendulumDateTime:
    _dt: datetime

    def subtract(self, days: int = 0, seconds: int = 0) -> "_PendulumDateTime":
        return _PendulumDateTime(self._dt - timedelta(days=days, seconds=seconds))

    def add(self, days: int = 0, seconds: int = 0) -> "_PendulumDateTime":
        return _PendulumDateTime(self._dt + timedelta(days=days, seconds=seconds))

    def __gt__(self, other: "_PendulumDateTime") -> bool:
        return self._dt > other._dt

    def __ge__(self, other: "_PendulumDateTime") -> bool:
        return self._dt >= other._dt

    def __lt__(self, other: "_PendulumDateTime") -> bool:
        return self._dt < other._dt

    def __le__(self, other: "_PendulumDateTime") -> bool:
        return self._dt <= other._dt

    def to_datetime_string(self) -> str:
        return self._dt.isoformat()

    def __str__(self) -> str:
        return self.to_datetime_string()


def now(tz: Optional[str] = None) -> _PendulumDateTime:
    dt = datetime.now(timezone.utc)
    return _PendulumDateTime(dt)
