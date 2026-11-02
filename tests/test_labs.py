"""Laboratórios práticos (roteiros em docs/laboratorios.md)."""

import logging
from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import permissions, viewsets
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.throttling import SimpleRateThrottle

from apps.processing import services as processing_services
from apps.processing.models import ProcessingJob
from apps.videos import selectors
from apps.videos import services as video_services
from apps.videos.api.serializers import VideoListSerializer
from apps.videos.api.views import VideoViewSet
from apps.videos.models import Video
from apps.videos.tests.factories import TagFactory, VideoFactory, VideoMetadataFactory

pytestmark = pytest.mark.django_db


# --------------------------------------------------------------------------- Lab 1


class IsOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.owner_id == request.user.id


class VulnerableVideoViewSet(viewsets.ReadOnlyModelViewSet):
    # SÓ PARA O LABORATÓRIO: protegido apenas por permissão de OBJETO, sem filtrar o queryset.
    queryset = Video.objects.all()
    serializer_class = VideoListSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]


class TestLab1ObjectPermissionDoesNotProtectList:
    @pytest.fixture
    def secret(self, other_user):
        return VideoFactory(owner=other_user, visibility="private", title="segredo do bob")

    def _call(self, viewset, action, user, **kwargs):
        request = APIRequestFactory().get("/")
        force_authenticate(request, user=user)
        return viewset.as_view({"get": action})(request, **kwargs)

    def test_vulnerable_list_leaks_private_videos(self, user, secret):
        response = self._call(VulnerableVideoViewSet, "list", user)
        titles = [v["title"] for v in response.data["results"]]
        # list não chama get_object() → has_object_permission nunca roda → vazou.
        assert "segredo do bob" in titles

    def test_vulnerable_retrieve_reveals_existence_with_403(self, user, secret):
        response = self._call(VulnerableVideoViewSet, "retrieve", user, pk=secret.pk)
        assert response.status_code == 403  # "existe, mas você não pode"

    def test_real_viewset_does_not_leak_and_answers_404(self, user, secret):
        listed = self._call(VideoViewSet, "list", user)
        detail = self._call(VideoViewSet, "retrieve", user, pk=secret.pk)
        assert "segredo do bob" not in [v["title"] for v in listed.data["results"]]
        assert detail.status_code == 404  # get_queryset filtrou: indistinguível de inexistente


# --------------------------------------------------------------------------- Lab 2


def test_lab2_middleware_sees_anonymous_but_view_sees_jwt_user(auth_client, user, caplog):
    caplog.set_level(logging.INFO, logger="clipstack.request")

    auth_client.get(reverse("users-me"))

    record = next(r for r in caplog.records if r.getMessage() == "request_finished")
    assert record.user_before_view == "anonymous"  # ida: só o AuthenticationMiddleware (sessão)
    assert record.user_after_view == f"user:{user.pk}"  # volta: o DRF copiou o usuário do JWT
    assert record.user_id == user.pk  # gravado pela ContextJWTAuthentication (camada do DRF)


# --------------------------------------------------------------------------- Lab 3


def test_lab3_upload_throttle_returns_429_with_retry_after(auth_client):
    # As taxas ficam num atributo de CLASSE lido no import; override_settings não as altera.
    rates = {**SimpleRateThrottle.THROTTLE_RATES, "upload": "2/hour"}
    with mock.patch.object(SimpleRateThrottle, "THROTTLE_RATES", rates):
        statuses = [
            auth_client.post(
                reverse("video-list"),
                {"title": "t", "file": SimpleUploadedFile("a.mp4", b"0")},
                format="multipart",
            )
            for _ in range(3)
        ]
    assert [r.status_code for r in statuses] == [201, 201, 429]
    assert int(statuses[-1].headers["Retry-After"]) > 0
    assert statuses[-1].data["error"]["code"] == "throttled"


# --------------------------------------------------------------------------- Lab 4


class TestLab4Cors:
    def test_preflight_from_allowed_origin(self, api_client):
        response = api_client.options(
            reverse("video-list"),
            HTTP_ORIGIN="http://localhost:5173",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization, idempotency-key",
        )
        assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
        assert "idempotency-key" in response.headers["Access-Control-Allow-Headers"]

    def test_disallowed_origin_gets_no_cors_headers_but_still_gets_data(self, api_client):
        response = api_client.get(reverse("meta"), HTTP_ORIGIN="https://evil.example")
        # O servidor responde normalmente: quem bloqueia é o NAVEGADOR (CORS não protege a API).
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" not in response.headers


# --------------------------------------------------------------------------- Lab 5


class TestLab5NPlusOne:
    def _seed(self, owner, n):
        tags = [TagFactory(name="a"), TagFactory(name="b")]
        for _ in range(n):
            VideoMetadataFactory(video=VideoFactory(owner=owner, tags=tags))

    @pytest.mark.parametrize("n_videos", [3, 15])
    def test_list_query_count_is_constant(
        self, auth_client, user, n_videos, django_assert_num_queries
    ):
        self._seed(user, n_videos)
        # 1 usuário do JWT + 1 COUNT da paginação + 1 lista (JOIN owner e metadata) + 1 tags.
        with django_assert_num_queries(4):
            response = auth_client.get(reverse("video-list"))
        assert response.data["count"] == n_videos

    def test_without_select_and_prefetch_it_grows_with_the_list(self, auth_client, user):
        self._seed(user, 15)

        def naive_queryset(*, user, with_jobs=False):
            return Video.objects.visible_to(user)  # sem select_related/prefetch_related

        with (
            mock.patch.object(selectors, "video_queryset", naive_queryset),
            CaptureQueriesContext(connection) as ctx,
        ):
            auth_client.get(reverse("video-list"))
        # 15 vídeos × (owner + metadata + tags) a mais: o N+1.
        assert len(ctx.captured_queries) > 40


# --------------------------------------------------------------------------- Lab 6


class TestLab6OnCommit:
    @pytest.fixture
    def enqueue(self):
        with mock.patch.object(processing_services, "enqueue_job") as enqueue:
            yield enqueue

    def _create(self, user):
        return video_services.create_video(
            owner=user, file=SimpleUploadedFile("a.mp4", b"0"), title="lab6"
        )

    def test_task_is_enqueued_only_after_commit(
        self, user, enqueue, django_capture_on_commit_callbacks
    ):
        with django_capture_on_commit_callbacks(execute=False) as callbacks:
            video = self._create(user)
            enqueue.assert_not_called()  # dentro da transação: nada foi publicado

        for callback in callbacks:  # simula o COMMIT
            callback()

        job = ProcessingJob.objects.get(video=video)
        enqueue.assert_called_once_with(job.pk)

    def test_nothing_is_enqueued_when_the_transaction_rolls_back(
        self, user, enqueue, django_capture_on_commit_callbacks
    ):
        with (
            django_capture_on_commit_callbacks(execute=True) as callbacks,
            pytest.raises(RuntimeError),
            transaction.atomic(),
        ):
            self._create(user)
            raise RuntimeError("falha depois de criar o vídeo")

        enqueue.assert_not_called()
        assert callbacks == []
        assert not Video.objects.filter(title="lab6").exists()


# --------------------------------------------------------------------------- Lab 7

PRIVATE, PUBLIC, FAILED = "private", "public", "failed"


@pytest.fixture
def actors(user, other_user, admin_user, client_for):
    return {
        "dono": client_for(user),
        "outro": client_for(other_user),
        "admin": client_for(admin_user),
    }


@pytest.fixture
def videos(user):
    return {
        PRIVATE: VideoFactory(owner=user, visibility="private"),
        PUBLIC: VideoFactory(owner=user),
        FAILED: VideoFactory(owner=user, status="failed"),
    }


@pytest.mark.parametrize(
    ("actor", "action", "video", "expected"),
    [
        ("dono", "get", PRIVATE, 200),
        ("outro", "get", PRIVATE, 404),
        ("admin", "get", PRIVATE, 200),
        ("dono", "patch", PUBLIC, 200),
        ("outro", "patch", PRIVATE, 404),
        ("outro", "patch", PUBLIC, 403),
        ("admin", "patch", PUBLIC, 403),
        ("outro", "delete", PUBLIC, 403),
        ("admin", "delete", PUBLIC, 204),
        ("dono", "delete", PUBLIC, 204),
        ("dono", "reprocess", FAILED, 202),
        ("admin", "reprocess", FAILED, 403),
    ],
)
def test_lab7_permission_matrix_404_vs_403(actors, videos, actor, action, video, expected):
    client, target = actors[actor], videos[video]
    url = reverse("video-detail", args=[target.pk])
    if action == "get":
        response = client.get(url)
    elif action == "patch":
        response = client.patch(url, {"title": "novo"}, format="json")
    elif action == "delete":
        response = client.delete(url)
    else:
        response = client.post(reverse("video-reprocess", args=[target.pk]))
    assert response.status_code == expected
