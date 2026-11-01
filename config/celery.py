"""App Celery do projeto.

O worker é um processo SEPARADO do servidor web (`celery -A config worker`), que carrega o
mesmo projeto Django (settings, ORM, services) e consome mensagens do RabbitMQ.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("clipstack")
# Lê do settings do Django tudo que começa com CELERY_ (CELERY_BROKER_URL → broker_url...).
app.config_from_object("django.conf:settings", namespace="CELERY")
# Procura tasks.py em cada app do INSTALLED_APPS.
app.autodiscover_tasks()
