"""Settings usados pelo pytest (definidos em pyproject.toml)."""

from .base import *  # noqa: F403

DEBUG = False

# Hasher MD5: inseguro, mas deixa a criação de usuários nos testes muito mais rápida.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Emails ficam em memória (django.core.mail.outbox / fixture mailoutbox do pytest-django).
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
