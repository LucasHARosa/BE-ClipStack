from datetime import timedelta
from unittest import mock

import pytest
from django.utils import timezone

from apps.processing import services
from apps.processing.exceptions import ProcessingAlreadyActive
from apps.processing.models import ProcessingJob
from apps.processing.processors import FakeVideoProcessor, ProcessingResult
from apps.processing.tests.factories import ProcessingJobFactory
from apps.videos.models import Video
from apps.videos.tests.factories import VideoFactory

pytestmark = pytest.mark.django_db


class StubProcessor:
    # Stub: resposta fixa, sem tocar no arquivo.
    def process(self, file_path, on_progress):
        on_progress(50)
        return ProcessingResult(duration_seconds=42, resolution="640x360", thumbnail=None)


class TestStartProcessing:
    def test_creates_queued_job_and_enqueues_after_commit(self, django_capture_on_commit_callbacks):
        video = VideoFactory(status=Video.Status.UPLOADED)
        with (
            mock.patch.object(services, "enqueue_job") as enqueue,
            django_capture_on_commit_callbacks() as callbacks,
        ):
            job = services.start_processing(video=video)
            assert enqueue.call_count == 0  # ainda dentro da transação
        assert job.status == ProcessingJob.Status.QUEUED
        # Dois callbacks: o enqueue e a invalidação do cache (o signal do vídeo, que mudou de
        # status). Rodar todos simula o COMMIT.
        for callback in callbacks:
            callback()
        enqueue.assert_called_once_with(job.pk)

    def test_second_active_job_hits_the_constraint(self):
        job = ProcessingJobFactory()
        with pytest.raises(ProcessingAlreadyActive):
            services.start_processing(video=job.video)
        # o savepoint isolou o erro: a transação continua utilizável
        assert ProcessingJob.objects.filter(video=job.video).count() == 1


class TestRunJob:
    def test_processor_injected_by_parameter(self):
        job = ProcessingJobFactory()

        done = services.run_job(job_id=job.pk, processor=StubProcessor())

        job.video.refresh_from_db()
        assert (done.status, done.progress, done.attempts) == ("completed", 100, 1)
        assert job.video.status == Video.Status.COMPLETED
        assert job.video.metadata.duration_seconds == 42

    def test_processor_from_settings(self, settings):
        settings.VIDEO_PROCESSOR_CLASS = "apps.processing.processors.FakeVideoProcessor"
        settings.FAKE_PROCESSOR_STEP_SECONDS = 0
        job = ProcessingJobFactory()

        services.run_job(job_id=job.pk)

        job.video.refresh_from_db()
        assert job.video.metadata.resolution == "1280x720"
        assert job.video.metadata.thumbnail.name.endswith(f"{job.video.pk}.jpg")

    def test_is_idempotent_for_finished_jobs(self):
        job = ProcessingJobFactory(status=ProcessingJob.Status.COMPLETED, attempts=1)
        processor = mock.Mock(spec=FakeVideoProcessor)

        services.run_job(job_id=job.pk, processor=processor)

        processor.process.assert_not_called()
        job.refresh_from_db()
        assert job.attempts == 1

    def test_attempts_incremented_in_the_database(self, django_assert_num_queries):
        job = ProcessingJobFactory(attempts=2)
        services.run_job(job_id=job.pk, processor=StubProcessor())
        job.refresh_from_db()
        assert job.attempts == 3


class TestFailJob:
    def test_marks_job_and_video_failed(self):
        job = ProcessingJobFactory(status=ProcessingJob.Status.PROCESSING)
        services.fail_job(job_id=job.pk, error_message="boom")
        job.refresh_from_db()
        job.video.refresh_from_db()
        assert (job.status, job.error_message) == ("failed", "boom")
        assert job.video.can_be_reprocessed()

    def test_does_not_touch_completed_jobs(self):
        job = ProcessingJobFactory(status=ProcessingJob.Status.COMPLETED)
        services.fail_job(job_id=job.pk, error_message="tarde demais")
        job.refresh_from_db()
        assert job.status == "completed"


def test_fail_stuck_jobs(settings):
    settings.STUCK_JOB_TIMEOUT_MINUTES = 15
    old = timezone.now() - timedelta(minutes=30)
    stuck = ProcessingJobFactory(status=ProcessingJob.Status.PROCESSING, started_at=old)
    recent = ProcessingJobFactory(status=ProcessingJob.Status.PROCESSING, started_at=timezone.now())

    assert services.fail_stuck_jobs() == 1

    stuck.refresh_from_db()
    recent.refresh_from_db()
    assert (stuck.status, recent.status) == ("failed", "processing")
