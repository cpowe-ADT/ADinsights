"""Celery tasks for Content Operations."""

from __future__ import annotations

from celery import shared_task

from accounts.tenant_context import tenant_context
from accounts.models import Tenant
from core.tasks import BaseAdInsightsTask

from .generation import (
    process_content_caption_generation_job as process_caption_generation_job,
)
from .metrics import refresh_published_post_metrics
from .models import GenerationJob, PublishedPost
from .publisher import (
    process_due_publish_attempts,
    process_facebook_page_publish_attempt,
    requeue_due_retryable_attempts,
)
from .scheduler import dispatch_due_schedules


class ContentOpsGenerationJobTask(BaseAdInsightsTask):
    """Tenant-aware task base for job-id-first Content Ops generation tasks."""

    abstract = True
    tenant_kwarg = None
    tenant_arg_index = -1


@shared_task(
    bind=True,
    base=BaseAdInsightsTask,
    max_retries=5,
    name="content_ops.tasks.dispatch_due_content_schedules",
)
def dispatch_due_content_schedules(self, tenant_id: str | None = None, limit: int = 100):
    """Create safe publish-attempt queue records for due Content Ops schedules."""

    if tenant_id:
        tenant_ids = [tenant_id]
    else:
        tenant_ids = list(Tenant.objects.values_list("id", flat=True))

    results = {}
    for current_tenant_id in tenant_ids:
        tenant = Tenant.objects.get(id=current_tenant_id)
        result = dispatch_due_schedules(tenant=tenant, limit=limit)
        results[str(current_tenant_id)] = result.as_dict()
    return results


@shared_task(
    bind=True,
    base=BaseAdInsightsTask,
    max_retries=5,
    name="content_ops.tasks.process_content_publish_attempt",
)
def process_content_publish_attempt(self, tenant_id: str, attempt_id: str):
    """Process one queued publish attempt through the disabled-by-default boundary."""

    tenant = Tenant.objects.get(id=tenant_id)
    result = process_facebook_page_publish_attempt(
        tenant=tenant,
        attempt_id=attempt_id,
    )
    return result.as_dict()


@shared_task(
    bind=True,
    base=BaseAdInsightsTask,
    max_retries=5,
    name="content_ops.tasks.process_due_content_publish_attempts",
)
def process_due_content_publish_attempts(
    self,
    tenant_id: str | None = None,
    limit: int = 100,
):
    """Process due queued publish attempts for one or all tenants."""

    if tenant_id:
        tenant_ids = [tenant_id]
    else:
        tenant_ids = list(Tenant.objects.values_list("id", flat=True))

    results = {}
    for current_tenant_id in tenant_ids:
        tenant = Tenant.objects.get(id=current_tenant_id)
        result = process_due_publish_attempts(tenant=tenant, limit=limit)
        results[str(current_tenant_id)] = result.as_dict()
    return results


@shared_task(
    bind=True,
    base=BaseAdInsightsTask,
    max_retries=5,
    name="content_ops.tasks.requeue_due_content_publish_attempts",
)
def requeue_due_content_publish_attempts(
    self,
    tenant_id: str | None = None,
    limit: int = 100,
):
    """Requeue due retryable publish attempts without calling a provider."""

    if tenant_id:
        tenant_ids = [tenant_id]
    else:
        tenant_ids = list(Tenant.objects.values_list("id", flat=True))

    results = {}
    for current_tenant_id in tenant_ids:
        tenant = Tenant.objects.get(id=current_tenant_id)
        result = requeue_due_retryable_attempts(tenant=tenant, limit=limit)
        results[str(current_tenant_id)] = result.as_dict()
    return results


@shared_task(
    bind=True,
    base=BaseAdInsightsTask,
    max_retries=5,
    name="content_ops.tasks.refresh_content_published_post_metrics",
)
def refresh_content_published_post_metrics(
    self,
    tenant_id: str | None = None,
    published_post_id: str | None = None,
    limit: int = 100,
):
    """Refresh Content Ops organic metric snapshots for published posts."""

    if published_post_id:
        post = PublishedPost.all_objects.select_related("tenant").get(id=published_post_id)
        if tenant_id is not None and str(post.tenant_id) != str(tenant_id):
            raise ValueError("published_post_tenant_mismatch")
        result = refresh_published_post_metrics(
            tenant=post.tenant,
            published_post_id=post.id,
        )
        return result.as_dict()

    if tenant_id:
        tenant_ids = [tenant_id]
    else:
        tenant_ids = list(Tenant.objects.values_list("id", flat=True))

    results = {}
    for current_tenant_id in tenant_ids:
        tenant = Tenant.objects.get(id=current_tenant_id)
        post_ids = list(
            PublishedPost.all_objects.filter(tenant=tenant)
            .order_by("last_metrics_refresh_at", "-published_at")
            .values_list("id", flat=True)[:limit]
        )
        refreshed = 0
        unavailable = 0
        for post_id in post_ids:
            result = refresh_published_post_metrics(
                tenant=tenant,
                published_post_id=post_id,
            )
            if result.status == "refreshed":
                refreshed += 1
            elif result.status == "unavailable":
                unavailable += 1
        results[str(current_tenant_id)] = {
            "scanned": len(post_ids),
            "refreshed": refreshed,
            "unavailable": unavailable,
        }
    return results


@shared_task(
    bind=True,
    base=ContentOpsGenerationJobTask,
    max_retries=5,
    name="content_ops.tasks.process_content_caption_generation_job",
)
def process_content_caption_generation_job(
    self,
    job_id: str,
    tenant_id: str | None = None,
):
    """Process one queued caption generation job without live provider activation."""

    job = GenerationJob.all_objects.only("tenant_id").filter(id=job_id).first()
    if job is None:
        result = process_caption_generation_job(job_id=job_id)
        return result.as_dict()
    if tenant_id is not None and str(job.tenant_id) != str(tenant_id):
        raise ValueError("generation_job_tenant_mismatch")
    with tenant_context(str(job.tenant_id)):
        result = process_caption_generation_job(job_id=job_id)
    return result.as_dict()


__all__ = [
    "dispatch_due_content_schedules",
    "process_content_caption_generation_job",
    "process_due_content_publish_attempts",
    "process_content_publish_attempt",
    "refresh_content_published_post_metrics",
    "requeue_due_content_publish_attempts",
]
