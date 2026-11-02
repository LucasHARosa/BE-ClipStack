from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.videos import services
from apps.videos.exceptions import VideoNotReprocessable
from apps.videos.models import Video
from apps.videos.tests.factories import TagFactory, VideoFactory

pytestmark = pytest.mark.django_db

FAKE_ENTRYPOINT = "apps.videos.tests.test_services.fake_start_processing"
started = mock.Mock()


def fake_start_processing(*, video):
    # Fake: registra a chamada e muda o status como o processing faria.
    started(video_id=video.pk)
    video.status = Video.Status.QUEUED
    video.save(update_fields=["status"])


@pytest.fixture(autouse=True)
def _fake_entrypoint(settings):
    started.reset_mock()
    settings.VIDEO_PROCESSING_ENTRYPOINT = FAKE_ENTRYPOINT


def test_create_video_saves_tags_and_starts_processing(user):
    vlog = TagFactory(name="vlog")
    video = services.create_video(
        owner=user,
        file=SimpleUploadedFile("a.mp4", b"0" * 10),
        title="Novo",
        tags=[vlog],
    )
    assert list(video.tags.all()) == [vlog]
    assert video.file.name.startswith(f"videos/{user.pk}/")
    started.assert_called_once_with(video_id=video.pk)
    video.refresh_from_db()
    assert video.status == Video.Status.QUEUED


def test_create_video_rolls_back_if_processing_fails(user):
    with (
        mock.patch(f"{__name__}.started", side_effect=RuntimeError("fila fora")),
        pytest.raises(RuntimeError),
    ):
        services.create_video(owner=user, file=SimpleUploadedFile("a.mp4", b"0"), title="X")
    assert not Video.objects.filter(title="X").exists()


def test_reprocess_only_failed_videos(user):
    video = VideoFactory(owner=user, status=Video.Status.COMPLETED)
    with pytest.raises(VideoNotReprocessable) as exc:
        services.reprocess_video(video_id=video.pk)
    assert exc.value.status_code == 409
    assert exc.value.details == {"status": "completed"}
    started.assert_not_called()


def test_reprocess_failed_video_starts_processing(user):
    video = VideoFactory(owner=user, status=Video.Status.FAILED)
    services.reprocess_video(video_id=video.pk)
    started.assert_called_once_with(video_id=video.pk)


def test_delete_is_soft(user):
    video = VideoFactory(owner=user)
    services.delete_video(video=video, actor=user)
    assert Video.objects.filter(pk=video.pk, is_deleted=True).exists()
    assert not Video.objects.alive().filter(pk=video.pk).exists()


def test_update_video_writes_only_given_fields(user):
    video = VideoFactory(owner=user, status=Video.Status.PROCESSING)
    # Outro processo (o worker) muda o status enquanto a edição acontece...
    Video.objects.filter(pk=video.pk).update(status=Video.Status.COMPLETED)
    services.update_video(video=video, data={"title": "Editado"})
    video.refresh_from_db()
    # ...e o update_fields não sobrescreve o status com o valor velho que estava em memória.
    assert (video.title, video.status) == ("Editado", Video.Status.COMPLETED)
