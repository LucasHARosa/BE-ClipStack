from .base import *  # noqa: F403

DEBUG = False

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"

VIDEO_PROCESSOR_CLASS = "apps.processing.processors.FakeVideoProcessor"
FAKE_PROCESSOR_STEP_SECONDS = 0

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
