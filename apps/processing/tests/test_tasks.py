"""Testes da task process_video rodando DIRETAMENTE (sem broker, sem worker).

process_video(job_id) executa a função na hora. process_video.apply(args=...) executa no modo
"eager" e simula os retries (o self.retry() reexecuta a task de forma síncrona, sem countdown).
"""

from unittest import mock

import pytest

from apps.processing import tasks
from apps.processing.exceptions import ProcessingError, TransientProcessingError
from apps.processing.models import ProcessingJob
from apps.processing.processors import ProcessingResult
from apps.processing.tests.factories import ProcessingJobFactory

pytestmark = pytest.mark.django_db

PROCESSOR_PATH = "apps.processing.tests.test_tasks.ScriptedProcessor"


class ScriptedProcessor:
    # Fake controlado pelo teste: cada chamada consome o próximo item do roteiro
    # (uma exceção para levantar ou "ok" para terminar com sucesso).
    script: list = []
    calls = 0

    def process(self, file_path, on_progress):
        type(self).calls += 1
        step = type(self).script.pop(0)
        if isinstance(step, Exception):
            raise step
        return ProcessingResult(duration_seconds=10, resolution="640x360", thumbnail=None)


@pytest.fixture
def scripted(settings):
    settings.VIDEO_PROCESSOR_CLASS = PROCESSOR_PATH
    ScriptedProcessor.calls = 0

    def set_script(*steps):
        ScriptedProcessor.script = list(steps)

    return set_script


def test_success(scripted):
    scripted("ok")
    job = ProcessingJobFactory()

    tasks.process_video(job.pk)

    job.refresh_from_db()
    assert job.status == ProcessingJob.Status.COMPLETED


def test_idempotent_second_delivery_does_nothing(scripted):
    scripted("ok")
    job = ProcessingJobFactory()
    tasks.process_video(job.pk)
    tasks.process_video(job.pk)  # mesma mensagem entregue de novo (acks_late)
    assert ScriptedProcessor.calls == 1


def test_transient_error_is_retried_then_succeeds(scripted):
    scripted(TransientProcessingError("ffmpeg ocupado"), "ok")
    job = ProcessingJobFactory()

    tasks.process_video.apply(args=[job.pk])

    job.refresh_from_db()
    assert job.status == ProcessingJob.Status.COMPLETED
    assert job.attempts == 2  # cada tentativa incrementa com F()


def test_retry_uses_exponential_backoff(scripted):
    scripted(TransientProcessingError("x"))
    job = ProcessingJobFactory()
    with (
        mock.patch.object(tasks.process_video, "retry", side_effect=RuntimeError) as retry,
        pytest.raises(RuntimeError),
    ):
        tasks.process_video(job.pk)
    countdown = retry.call_args.kwargs["countdown"]
    assert tasks.BACKOFF_BASE_SECONDS <= countdown <= 2 * tasks.BACKOFF_BASE_SECONDS


def test_exhausted_retries_mark_failed(scripted):
    max_retries = tasks.process_video.max_retries
    scripted(*[TransientProcessingError("fora")] * (max_retries + 1))
    job = ProcessingJobFactory()

    tasks.process_video.apply(args=[job.pk])

    job.refresh_from_db()
    assert job.status == ProcessingJob.Status.FAILED
    assert f"após {max_retries + 1} tentativas" in job.error_message
    assert ScriptedProcessor.calls == max_retries + 1


def test_permanent_error_fails_without_retry(scripted):
    scripted(ProcessingError("arquivo corrompido"))
    job = ProcessingJobFactory()

    tasks.process_video.apply(args=[job.pk])

    job.refresh_from_db()
    assert (job.status, job.error_message) == ("failed", "arquivo corrompido")
    assert ScriptedProcessor.calls == 1


def test_backoff_is_capped():
    assert tasks.backoff_seconds(20) <= tasks.BACKOFF_MAX_SECONDS + tasks.BACKOFF_BASE_SECONDS
