# Carrega o app Celery junto com o Django, para que @shared_task use este app (e as
# configurações dele) quando um service publicar uma task.
from .celery import app as celery_app

__all__ = ("celery_app",)
