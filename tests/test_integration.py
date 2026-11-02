"""Integração: upload pela API → job → task → completed → notificação → email.

Camadas reais (API, services, task, banco). Só a FRONTEIRA com o broker é substituída: o
.delay() de cada task executa a task na hora, em vez de publicar no RabbitMQ.
"""

from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.notifications import tasks as notification_tasks
from apps.notifications.models import Notification
from apps.processing import tasks as processing_tasks
from apps.processing.models import ProcessingJob
from apps.videos.models import Video

pytestmark = pytest.mark.django_db


@pytest.fixture
def run_tasks_inline():
    def inline(task):
        return mock.patch.object(task, "delay", side_effect=lambda *args: task(*args))

    with (
        inline(processing_tasks.process_video),
        inline(notification_tasks.notify_video_processed),
        inline(notification_tasks.send_notification_email),
    ):
        yield


def test_upload_to_completed_with_notification_and_email(
    auth_client, user, mailoutbox, run_tasks_inline, django_capture_on_commit_callbacks
):
    # execute=True: os on_commit rodam ao sair do bloco, inclusive os registrados DURANTE a
    # execução dos anteriores (enqueue → task → notificação → email).
    with django_capture_on_commit_callbacks(execute=True):
        response = auth_client.post(
            reverse("video-list"),
            {"title": "Integração", "file": SimpleUploadedFile("a.mp4", b"0" * 200_000)},
            format="multipart",
        )
        assert response.status_code == 201
        assert response.data["status"] == "queued"

    video = Video.objects.get(pk=response.data["id"])
    job = ProcessingJob.objects.get(video=video)
    assert video.status == Video.Status.COMPLETED
    assert (job.status, job.progress, job.attempts) == ("completed", 100, 1)
    assert video.metadata.resolution == "1280x720"  # FakeVideoProcessor (settings de teste)

    notification = Notification.objects.get(user=user)
    assert notification.event_key == f"job:{job.pk}:finished"
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == [user.email]

    detail = auth_client.get(reverse("video-detail", args=[video.pk])).data
    assert detail["latest_job"]["status"] == "completed"
    assert detail["can_reprocess"] is False
