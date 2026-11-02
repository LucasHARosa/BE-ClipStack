# Para o @shared_task usar este app quando o Django publicar uma task.
from .celery import app as celery_app

__all__ = ("celery_app",)
