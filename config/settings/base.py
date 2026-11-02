from datetime import timedelta
from pathlib import Path

import environ
from corsheaders.defaults import default_headers

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

# ---------------------------------------------------------------- apps
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]
THIRD_PARTY_APPS = [
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
]
LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.videos",
    "apps.processing",
    "apps.notifications",
]
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ---------------------------------------------------------------- middleware
MIDDLEWARE = [
    # Primeiro: põe os headers CORS também nas respostas de erro dos outros middlewares.
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.middleware.RequestIdMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------- banco
DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------- cache
# Redis, não cache local: com vários workers do Gunicorn, cada um teria o próprio contador de
# throttling (limite efetivo N vezes maior).
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://localhost:6379/0"),
        "KEY_PREFIX": "clipstack",
    }
}

# ---------------------------------------------------------------- autenticação
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------- i18n
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------- arquivos
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = env.path("MEDIA_ROOT", default=BASE_DIR / "media")
# Só para o compose local (DEBUG=False). Em produção, a mídia sai do storage/CDN.
SERVE_MEDIA = env.bool("SERVE_MEDIA", default=False)

# ---------------------------------------------------------------- CORS
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=["http://localhost:5173"])
CORS_ALLOW_HEADERS = (*default_headers, "idempotency-key", "x-request-id")
CORS_EXPOSE_HEADERS = ["X-Request-ID", "Idempotent-Replayed", "Retry-After"]

# ---------------------------------------------------------------- upload de vídeos
VIDEO_ALLOWED_EXTENSIONS = env.list(
    "VIDEO_ALLOWED_EXTENSIONS", default=[".mp4", ".mov", ".webm", ".mkv"]
)
VIDEO_MAX_UPLOAD_SIZE_MB = env.int("VIDEO_MAX_UPLOAD_SIZE_MB", default=200)
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# ---------------------------------------------------------------- processamento de vídeos
VIDEO_PROCESSOR_CLASS = env(
    "VIDEO_PROCESSOR_CLASS", default="apps.processing.processors.FakeVideoProcessor"
)
FAKE_PROCESSOR_STEP_SECONDS = env.float("FAKE_PROCESSOR_STEP_SECONDS", default=1.0)
# videos não pode importar processing (import-linter): a ligação entre as apps fica aqui.
VIDEO_PROCESSING_ENTRYPOINT = "apps.processing.services.start_processing"

# ---------------------------------------------------------------- DRF
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.core.authentication.ContextJWTAuthentication",
    ],
    # Fechado por padrão: endpoint público precisa declarar AllowAny.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.DefaultPagination",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "EXCEPTION_HANDLER": "apps.core.exception_handler.api_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("THROTTLE_ANON", default="30/minute"),
        # Folga para o polling do frontend (1 GET a cada 2 s = 30/min por vídeo aberto).
        "user": env("THROTTLE_USER", default="120/minute"),
        "upload": env("THROTTLE_UPLOAD", default="10/hour"),
        "login": env("THROTTLE_LOGIN", default="5/minute"),
    },
}

# ---------------------------------------------------------------- Celery
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="amqp://clipstack:clipstack@localhost:5672//")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://localhost:6379/1")
CELERY_RESULT_EXPIRES = 60 * 60 * 24
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE

# Fila própria para o vídeo: com uma fila só, vídeos na frente atrasariam os emails.
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_ROUTES = {"apps.processing.tasks.process_video": {"queue": "processing"}}

# Tasks longas: com o padrão (4), mensagens ficariam presas num worker ocupado.
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_REJECT_ON_WORKER_LOST = True
# RabbitMQ 4 recusa as filas "transient non-exclusive" que o Celery usa no controle remoto
# e nos eventos.
CELERY_CONTROL_QUEUE_EXCLUSIVE = True
CELERY_EVENT_QUEUE_EXCLUSIVE = True
CELERY_WORKER_CANCEL_LONG_RUNNING_TASKS_ON_CONNECTION_LOSS = True
CELERY_TASK_SOFT_TIME_LIMIT = 10 * 60
CELERY_TASK_TIME_LIMIT = 11 * 60

# Rodar UMA instância do beat; duas publicariam tudo em dobro.
CELERY_BEAT_SCHEDULE = {
    "fail-stuck-processing-jobs": {
        "task": "apps.processing.tasks.fail_stuck_jobs",
        "schedule": 5 * 60,
    },
    "purge-old-idempotency-keys": {
        "task": "apps.core.tasks.purge_idempotency_keys",
        "schedule": 60 * 60,
    },
}
# Precisa ser maior que CELERY_TASK_TIME_LIMIT + o maior backoff de retry.
STUCK_JOB_TIMEOUT_MINUTES = env.int("STUCK_JOB_TIMEOUT_MINUTES", default=15)
IDEMPOTENCY_KEY_TTL_HOURS = 24

# ---------------------------------------------------------------- email
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="ClipStack <no-reply@clipstack.local>")

# ---------------------------------------------------------------- logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_context": {"()": "apps.core.logs.RequestContextFilter"}},
    "formatters": {"json": {"()": "apps.core.logs.JsonFormatter"}},
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["request_context"],
        }
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
    "loggers": {
        # O RequestIdMiddleware já loga cada requisição.
        "django.request": {"level": "ERROR"},
        "django.server": {"level": "WARNING"},
    },
}

# ---------------------------------------------------------------- OpenAPI
SPECTACULAR_SETTINGS = {
    "TITLE": "ClipStack API",
    "DESCRIPTION": "Upload e processamento assíncrono de vídeos (Django, DRF, Celery, RabbitMQ).",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_NAME_OVERRIDES": {
        "VideoStatusEnum": "apps.videos.models.Video.Status",
        "JobStatusEnum": "apps.processing.models.ProcessingJob.Status",
    },
}

# ---------------------------------------------------------------- JWT (simplejwt)
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env.int("JWT_ACCESS_MINUTES", default=15)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env.int("JWT_REFRESH_DAYS", default=7)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}
