"""Settings usados pelo pytest (definidos em pyproject.toml)."""

from .base import *  # noqa: F403

DEBUG = False

# Hasher MD5: inseguro, mas deixa a criação de usuários nos testes muito mais rápida.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Cache em memória: os testes não dependem de um Redis rodando (e cada processo de teste
# tem o seu, sem vazar contadores de throttling entre execuções).
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# Broker em memória: publicar uma task nos testes não precisa de RabbitMQ (os testes chamam
# as tasks diretamente ou mockam o .delay/.apply_async).
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"

# Processador fake sem espera: os testes não dormem.
VIDEO_PROCESSOR_CLASS = "apps.processing.processors.FakeVideoProcessor"
FAKE_PROCESSOR_STEP_SECONDS = 0

# Emails ficam em memória (django.core.mail.outbox / fixture mailoutbox do pytest-django).
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
