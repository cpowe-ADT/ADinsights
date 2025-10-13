from __future__ import annotations

from celery import shared_task

from .services import AlertService


@shared_task(bind=True)
def run_alert_cycle(self):
    """Evaluate alert rules and persist run metadata."""

    service = AlertService()
    runs = service.run_cycle()
    return [
        {
            "id": str(run.id),
            "rule": run.rule_slug,
            "status": run.status,
            "row_count": run.row_count,
            "duration_ms": run.duration_ms,
        }
        for run in runs
    ]


__all__ = ["run_alert_cycle"]
