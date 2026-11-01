"""Management command: processa jobs de forma síncrona, sem fila.

Uso: manage.py process_job 12 13   |   manage.py process_job --queued
Útil em desenvolvimento e para reprocessar algo à mão em produção. Um management command é o
equivalente a um script de CLI que já carrega o Django (settings, ORM).
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils.module_loading import import_string

from apps.processing import services
from apps.processing.exceptions import ProcessingError
from apps.processing.models import ProcessingJob


class Command(BaseCommand):
    help = "Processa jobs de vídeo de forma síncrona (sem Celery)."

    def add_arguments(self, parser):
        parser.add_argument("job_ids", nargs="*", type=int)
        parser.add_argument("--queued", action="store_true", help="Processa todos os 'queued'.")
        parser.add_argument("--processor", help="Caminho da classe do processador (opcional).")

    def handle(self, *args, job_ids, queued, processor, **options):
        if queued:
            job_ids = list(
                ProcessingJob.objects.filter(status=ProcessingJob.Status.QUEUED).values_list(
                    "pk", flat=True
                )
            )
            if not job_ids:
                self.stdout.write("Nenhum job na fila.")
                return
        if not job_ids:
            raise CommandError("Informe ids de jobs ou --queued.")

        instance = import_string(processor)() if processor else None
        for job_id in job_ids:
            try:
                job = services.run_job(job_id=job_id, processor=instance)
            except ProcessingError as exc:
                job = services.fail_job(job_id=job_id, error_message=str(exc))
            self.stdout.write(f"job {job.pk}: {job.status} ({job.progress}%) {job.error_message}")
