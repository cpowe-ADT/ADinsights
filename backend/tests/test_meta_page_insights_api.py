from __future__ import annotations

from datetime import datetime, timezone as dt_timezone

import pytest
from django.urls import reverse

from accounts.models import Tenant, User
from integrations.models import (
    MetaConnection,
    MetaInsightPoint,
    MetaPage,
    MetaPost,
    MetaPostInsightPoint,
)


def _authenticate(api_client, *, username: str, password: str) -> None:
    token = api_client.post(
        reverse("token_obtain_pair"),
        {"username": username, "password": password},
        format="json",
    ).json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


def _create_user(*, tenant: Tenant, username: str) -> User:
    user = User.objects.create_user(username=username, email=username, tenant=tenant)
    user.set_password("password123")
    user.save()
    return user


def _create_page_for_user(user: User) -> MetaPage:
    connection = MetaConnection(
        tenant=user.tenant,
        user=user,
        app_scoped_user_id=f"app-{user.id}",
        scopes=["read_insights", "pages_read_engagement"],
        is_active=True,
    )
    connection.set_raw_token("user-token")
    connection.save()

    page = MetaPage(
        tenant=user.tenant,
        connection=connection,
        page_id="page-1",
        name="Business Page",
        can_analyze=True,
        tasks=["ANALYZE"],
        is_default=True,
    )
    page.set_raw_page_token("page-token")
    page.save()
    return page


@pytest.mark.django_db
def test_meta_oauth_callback_creates_connection_and_pages(api_client, user, monkeypatch, settings):
    _authenticate(api_client, username="user@example.com", password="password123")
    settings.META_APP_ID = "meta-app-id"
    settings.META_APP_SECRET = "meta-app-secret"
    settings.META_LOGIN_CONFIG_ID = "2323589144820085"
    settings.META_LOGIN_CONFIG_REQUIRED = True
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"

    start_response = api_client.post(reverse("meta-oauth-start"), {}, format="json")
    assert start_response.status_code == 200
    state = start_response.json()["state"]

    class DummyPage:
        id = "page-1"
        name = "Business Page"
        access_token = "page-access-token"
        tasks = ["ANALYZE"]
        perms = ["ADMINISTER"]

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def exchange_code(self, *, code: str, redirect_uri: str):
            assert code == "oauth-code"
            return type("Token", (), {"access_token": "short-token", "expires_in": 3600})()

        def exchange_for_long_lived_user_token(self, *, short_lived_user_token: str):
            return type("Token", (), {"access_token": "long-token", "expires_in": 7200})()

        def debug_token(self, *, input_token: str):
            return {"is_valid": True, "user_id": "meta-user-1"}

        def list_permissions(self, *, user_access_token: str):
            return [
                {"permission": "read_insights", "status": "granted"},
                {"permission": "pages_read_engagement", "status": "granted"},
            ]

        def list_pages(self, *, user_access_token: str):
            return [DummyPage()]

    monkeypatch.setattr("integrations.meta_page_views.MetaGraphClient.from_settings", lambda: DummyClient())

    response = api_client.get(
        reverse("meta-oauth-callback"),
        {"code": "oauth-code", "state": state},
        format="json",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["pages"][0]["page_id"] == "page-1"
    assert "page_token" not in str(payload)

    connection = MetaConnection.objects.get(tenant=user.tenant)
    assert connection.decrypt_token() == "long-token"
    page = MetaPage.objects.get(tenant=user.tenant, page_id="page-1")
    assert page.decrypt_page_token() == "page-access-token"


@pytest.mark.django_db
def test_meta_connect_callback_persists_pages_without_ad_account_requirement(
    api_client,
    user,
    monkeypatch,
    settings,
):
    _authenticate(api_client, username="user@example.com", password="password123")
    settings.META_APP_ID = "meta-app-id"
    settings.META_APP_SECRET = "meta-app-secret"
    settings.META_LOGIN_CONFIG_REQUIRED = False
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"

    start_response = api_client.post(reverse("meta-connect-start"), {}, format="json")
    assert start_response.status_code == 200
    state = start_response.json()["state"]

    class DummyPage:
        id = "page-1"
        name = "Business Page"
        access_token = "page-access-token"
        tasks = []
        perms = ["ADMINISTER"]

    class DummyTask:
        def __init__(self, task_id: str):
            self.id = task_id

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def exchange_code(self, *, code: str, redirect_uri: str):
            assert code == "oauth-code"
            return type("Token", (), {"access_token": "short-token", "expires_in": 3600})()

        def exchange_for_long_lived_user_token(self, *, short_lived_user_token: str):
            return type("Token", (), {"access_token": "long-token", "expires_in": 7200})()

        def debug_token(self, *, input_token: str):
            return {"is_valid": True, "user_id": "meta-user-1"}

        def list_permissions(self, *, user_access_token: str):
            return [
                {"permission": "pages_read_engagement", "status": "granted"},
            ]

        def list_pages(self, *, user_access_token: str):
            return [DummyPage()]

    monkeypatch.setattr("integrations.meta_page_views.MetaGraphClient.from_settings", lambda: DummyClient())
    monkeypatch.setattr(
        "integrations.meta_page_views.sync_page_posts.delay",
        lambda **kwargs: DummyTask("task-posts"),
    )
    monkeypatch.setattr(
        "integrations.meta_page_views.discover_supported_metrics.delay",
        lambda **kwargs: DummyTask("task-discover"),
    )
    monkeypatch.setattr(
        "integrations.meta_page_views.sync_page_insights.delay",
        lambda **kwargs: DummyTask("task-page"),
    )
    monkeypatch.setattr(
        "integrations.meta_page_views.sync_post_insights.delay",
        lambda **kwargs: DummyTask("task-post-insights"),
    )

    response = api_client.post(
        reverse("meta-connect-callback"),
        {"code": "oauth-code", "state": state},
        format="json",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["default_page_id"] == "page-1"
    assert payload["tasks"]["sync_page_insights"] == "task-page"
    page = MetaPage.objects.get(tenant=user.tenant, page_id="page-1")
    assert page.can_analyze is True


@pytest.mark.django_db
def test_meta_pages_select_overview_timeseries_posts_and_refresh(api_client, user, monkeypatch):
    _authenticate(api_client, username="user@example.com", password="password123")
    page = _create_page_for_user(user)

    MetaInsightPoint.all_objects.create(
        tenant=user.tenant,
        page=page,
        metric_key="page_post_engagements",
        period="day",
        end_time=datetime(2026, 2, 18, 8, 0, tzinfo=dt_timezone.utc),
        value_num=100,
        breakdown_key_normalized="__none__",
    )

    post = MetaPost.all_objects.create(
        tenant=user.tenant,
        page=page,
        post_id="page-1_111",
        created_time=datetime(2026, 2, 18, 8, 0, tzinfo=dt_timezone.utc),
        message="hello",
        permalink_url="https://example.com/post/111",
    )
    MetaPostInsightPoint.all_objects.create(
        tenant=user.tenant,
        post=post,
        metric_key="post_reactions_like_total",
        period="lifetime",
        end_time=datetime(2026, 2, 18, 8, 0, tzinfo=dt_timezone.utc),
        value_num=44,
        breakdown_key_normalized="__none__",
    )

    pages_response = api_client.get(reverse("meta-pages"))
    assert pages_response.status_code == 200
    assert len(pages_response.json()["pages"]) == 1

    select_response = api_client.post(
        reverse("meta-page-select", kwargs={"page_id": "page-1"}),
        {},
        format="json",
    )
    assert select_response.status_code == 200

    overview_response = api_client.get(
        reverse("meta-page-overview", kwargs={"page_id": "page-1"}),
        {"date_preset": "last_28d"},
    )
    assert overview_response.status_code == 200
    assert "cards" in overview_response.json()

    timeseries_response = api_client.get(
        reverse("meta-page-timeseries", kwargs={"page_id": "page-1"}),
        {"metric": "page_post_engagements", "period": "day"},
    )
    assert timeseries_response.status_code == 200
    assert len(timeseries_response.json()["points"]) >= 1

    posts_response = api_client.get(reverse("meta-page-posts", kwargs={"page_id": "page-1"}))
    assert posts_response.status_code == 200
    assert len(posts_response.json()["results"]) == 1

    post_ts_response = api_client.get(
        reverse("meta-post-timeseries", kwargs={"post_id": "page-1_111"}),
        {"metric": "post_reactions_like_total", "period": "lifetime"},
    )
    assert post_ts_response.status_code == 200
    assert len(post_ts_response.json()["points"]) == 1

    class DummyTaskResult:
        def __init__(self, task_id: str):
            self.id = task_id

    monkeypatch.setattr(
        "integrations.meta_page_views.sync_meta_page_insights.delay",
        lambda **kwargs: DummyTaskResult("task-page-1"),
    )
    monkeypatch.setattr(
        "integrations.meta_page_views.sync_meta_post_insights.delay",
        lambda **kwargs: DummyTaskResult("task-post-1"),
    )

    refresh_response = api_client.post(
        reverse("meta-page-refresh", kwargs={"page_id": "page-1"}),
        {"mode": "incremental"},
        format="json",
    )
    assert refresh_response.status_code == 202
    assert refresh_response.json()["page_task_id"] == "task-page-1"
    assert refresh_response.json()["post_task_id"] == "task-post-1"


@pytest.mark.django_db
def test_meta_page_endpoints_are_tenant_scoped(api_client):
    tenant_a = Tenant.objects.create(name="Tenant A")
    tenant_b = Tenant.objects.create(name="Tenant B")
    user_a = _create_user(tenant=tenant_a, username="a@example.com")
    _create_user(tenant=tenant_b, username="b@example.com")

    _create_page_for_user(user_a)

    _authenticate(api_client, username="b@example.com", password="password123")
    response = api_client.get(reverse("meta-page-overview", kwargs={"page_id": "page-1"}))
    assert response.status_code == 404

    # sanity check: owner tenant can read
    _authenticate(api_client, username="a@example.com", password="password123")
    ok = api_client.get(reverse("meta-page-overview", kwargs={"page_id": "page-1"}))
    assert ok.status_code == 200
