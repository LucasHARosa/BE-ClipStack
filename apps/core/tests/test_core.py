from datetime import timedelta
from unittest import mock

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core import health
from apps.core.models import IdempotencyKey
from apps.core.tasks import purge_idempotency_keys

pytestmark = pytest.mark.django_db


class TestErrorFormat:
    @pytest.mark.parametrize(
        ("method", "url_name", "status", "code"),
        [
            ("get", "video-list", 401, "not_authenticated"),
            ("get", "users-me", 401, "not_authenticated"),
        ],
    )
    def test_auth_errors(self, api_client, method, url_name, status, code):
        response = getattr(api_client, method)(reverse(url_name))
        assert response.status_code == status
        assert set(response.data["error"]) == {"code", "message", "details"}
        assert response.data["error"]["code"] == code

    def test_404_and_405(self, auth_client):
        assert auth_client.get(reverse("video-detail", args=[999999])).data["error"]["code"] == (
            "not_found"
        )
        assert auth_client.put(reverse("users-me"), {}).data["error"]["code"] == (
            "method_not_allowed"
        )

    def test_unhandled_exception_is_500_json_when_not_debug(self, auth_client, settings):
        settings.DEBUG = False
        with mock.patch("apps.videos.selectors.dashboard_stats", side_effect=RuntimeError("bug")):
            response = auth_client.get(reverse("dashboard-stats"))
        assert response.status_code == 500
        assert response.data["error"]["code"] == "server_error"


class TestRequestId:
    def test_generates_and_propagates(self, api_client):
        generated = api_client.get(reverse("meta"))
        propagated = api_client.get(reverse("meta"), HTTP_X_REQUEST_ID="abc-123")
        unsafe = api_client.get(reverse("meta"), HTTP_X_REQUEST_ID="<script>")

        assert len(generated.headers["X-Request-ID"]) == 32
        assert propagated.headers["X-Request-ID"] == "abc-123"
        assert unsafe.headers["X-Request-ID"] != "<script>"


def test_purge_idempotency_keys_removes_only_old_ones(user, settings):
    settings.IDEMPOTENCY_KEY_TTL_HOURS = 24
    fields = {"user": user, "request_path": "/", "response_status": 201, "response_snapshot": {}}
    old = IdempotencyKey.objects.create(key="velha", **fields)
    IdempotencyKey.objects.filter(pk=old.pk).update(
        created_at=timezone.now() - timedelta(hours=25)  # auto_now_add ignora valor no create
    )
    IdempotencyKey.objects.create(key="nova", **fields)

    assert purge_idempotency_keys() == 1  # task chamada direto, sem broker
    assert list(IdempotencyKey.objects.values_list("key", flat=True)) == ["nova"]


class TestHealth:
    URL = reverse("health")

    def test_ok_when_all_dependencies_respond(self, api_client):
        # Stubs: os checks reais (Redis, RabbitMQ) não existem no ambiente de testes.
        async def ok():
            return None

        with (
            mock.patch.object(health, "_check_database", lambda: None),
            mock.patch.object(health, "_check_redis", ok),
            mock.patch.object(health, "_check_rabbitmq", lambda: None),
        ):
            response = api_client.get(self.URL)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_503_when_one_dependency_is_down(self, api_client):
        async def ok():
            return None

        def down():
            raise ConnectionError("recusado")

        with (
            mock.patch.object(health, "_check_database", lambda: None),
            mock.patch.object(health, "_check_redis", ok),
            mock.patch.object(health, "_check_rabbitmq", down),
        ):
            response = api_client.get(self.URL)
        body = response.json()
        assert response.status_code == 503
        assert body["status"] == "degraded"
        assert body["checks"]["rabbitmq"]["ok"] is False
        assert body["checks"]["database"]["ok"] is True
