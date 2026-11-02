import uuid

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.videos.models import Video
from apps.videos.tests.factories import CommentFactory, TagFactory, VideoFactory

pytestmark = pytest.mark.django_db

LIST = reverse("video-list")


def detail(video):
    return reverse("video-detail", args=[video.pk])


def upload(client, name="clip.mp4", size=100, key=None, **fields):
    data = {"title": "Meu vídeo", "file": SimpleUploadedFile(name, b"0" * size), **fields}
    headers = {"HTTP_IDEMPOTENCY_KEY": key} if key else {}
    return client.post(LIST, data, format="multipart", **headers)


class TestUpload:
    def test_creates_video_queued_with_job(self, auth_client):
        response = upload(auth_client, tags=["vlog"])
        assert response.status_code == 201
        assert response.data["status"] == "queued"
        assert response.data["latest_job"]["status"] == "queued"
        assert response.data["tags"] == ["vlog"]
        assert response.data["is_owner"] is True

    @pytest.mark.parametrize(
        ("name", "size", "field"),
        [("virus.exe", 10, "file"), ("sem-extensao", 10, "file")],
    )
    def test_rejects_invalid_files(self, auth_client, name, size, field):
        response = upload(auth_client, name=name, size=size)
        assert response.status_code == 400
        assert field in response.data["error"]["details"]

    def test_rejects_files_over_the_limit(self, auth_client, settings):
        settings.VIDEO_MAX_UPLOAD_SIZE_MB = 0
        response = upload(auth_client, size=2048)
        assert response.status_code == 400
        assert "file" in response.data["error"]["details"]

    def test_unknown_tag_is_400(self, auth_client):
        assert upload(auth_client, tags=["nao-existe"]).status_code == 400


class TestIdempotencyKey:
    def test_same_key_returns_the_original_response(self, auth_client, user):
        key = str(uuid.uuid4())
        first = upload(auth_client, key=key)
        second = upload(auth_client, key=key)

        assert first.status_code == second.status_code == 201
        assert first.data["id"] == second.data["id"]
        assert second.headers["Idempotent-Replayed"] == "true"
        assert Video.objects.filter(owner=user).count() == 1

    def test_failed_request_does_not_burn_the_key(self, auth_client, user):
        key = str(uuid.uuid4())
        assert upload(auth_client, name="x.exe", key=key).status_code == 400
        assert upload(auth_client, key=key).status_code == 201

    def test_same_key_from_another_user_is_independent(self, auth_client, other_client):
        key = str(uuid.uuid4())
        assert upload(auth_client, key=key).data["id"] != upload(other_client, key=key).data["id"]


class TestListFiltersAndPagination:
    def test_paginated_response(self, auth_client, user, settings):
        VideoFactory.create_batch(3, owner=user)
        response = auth_client.get(LIST, {"page_size": 2})
        assert response.data["count"] == 3
        assert len(response.data["results"]) == 2
        assert response.data["next"] is not None

    def test_filters_search_and_ordering(self, auth_client, user):
        vlog = TagFactory(name="vlog")
        VideoFactory(owner=user, title="Viagem", tags=[vlog, TagFactory(name="música")])
        VideoFactory(owner=user, title="Tutorial", status="failed")

        def titles(**params):
            return [v["title"] for v in auth_client.get(LIST, params).data["results"]]

        assert titles(tag="vlog") == ["Viagem"]  # distinct: aparece uma vez só
        assert titles(status="failed") == ["Tutorial"]
        assert titles(search="viag") == ["Viagem"]
        assert titles(ordering="title") == ["Tutorial", "Viagem"]

    def test_invalid_filter_value_is_400(self, auth_client):
        assert auth_client.get(LIST, {"status": "xyz"}).status_code == 400

    def test_mine_filter(self, auth_client, user, other_user):
        VideoFactory(owner=user, title="meu")
        VideoFactory(owner=other_user, title="dele")
        results = auth_client.get(LIST, {"mine": "true"}).data["results"]
        assert [v["title"] for v in results] == ["meu"]


class TestComments:
    def test_create_uses_request_user_as_author(self, auth_client, user, other_user):
        video = VideoFactory(owner=other_user)
        url = reverse("video-comments-list", args=[video.pk])
        response = auth_client.post(url, {"text": "Ótimo!", "author": other_user.pk}, format="json")
        assert response.status_code == 201
        assert response.data["author"] == user.pk

    def test_cannot_comment_on_invisible_video(self, auth_client, other_user):
        video = VideoFactory(owner=other_user, visibility="private")
        url = reverse("video-comments-list", args=[video.pk])
        assert auth_client.post(url, {"text": "oi"}, format="json").status_code == 404

    def test_comments_have_no_update(self, auth_client, user):
        comment = CommentFactory(author=user)
        url = reverse("video-comments-detail", args=[comment.video_id, comment.pk])
        assert auth_client.patch(url, {"text": "x"}, format="json").status_code == 405


class TestTags:
    def test_users_read_admins_write(self, auth_client, admin_client):
        assert auth_client.get(reverse("tag-list")).status_code == 200
        assert (
            auth_client.post(reverse("tag-list"), {"name": "x"}, format="json").status_code == 403
        )
        assert (
            admin_client.post(reverse("tag-list"), {"name": "x"}, format="json").status_code == 201
        )


class TestDashboardStats:
    URL = reverse("dashboard-stats")

    def test_aggregates(self, auth_client, user, other_user):
        VideoFactory(owner=user, status="failed")
        video = VideoFactory(owner=user)
        CommentFactory.create_batch(2, video=video, author=other_user)
        VideoFactory(owner=other_user)  # não entra nas estatísticas da alice

        data = auth_client.get(self.URL).data

        assert data["total_videos"] == 2
        assert data["by_status"]["failed"] == 1
        assert data["top_commented"] == [
            {"id": video.pk, "title": video.title, "comments_count": 2}
        ]

    def test_cached_and_invalidated_by_signal(
        self,
        auth_client,
        user,
        other_user,
        django_assert_num_queries,
        django_capture_on_commit_callbacks,
    ):
        video = VideoFactory(owner=user)
        auth_client.get(self.URL)  # miss: calcula e grava no cache

        # hit: só a query de autenticação (busca do usuário do JWT), nenhuma de estatística
        with django_assert_num_queries(1):
            auth_client.get(self.URL)

        # o signal agenda a invalidação para depois do commit
        with django_capture_on_commit_callbacks(execute=True):
            CommentFactory(video=video, author=other_user)

        assert auth_client.get(self.URL).data["top_commented"][0]["comments_count"] == 1
