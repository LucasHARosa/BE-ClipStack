"""Settings usados pelo pytest (definidos em pyproject.toml)."""

from .base import *  # noqa: F403

DEBUG = False

# Hasher MD5: inseguro, mas deixa a criação de usuários nos testes muito mais rápida.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Processador fake sem espera: os testes não dormem.
VIDEO_PROCESSOR_CLASS = "apps.processing.processors.FakeVideoProcessor"
FAKE_PROCESSOR_STEP_SECONDS = 0

# Emails ficam em memória (django.core.mail.outbox / fixture mailoutbox do pytest-django).
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
